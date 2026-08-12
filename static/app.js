(() => {
  const form = document.getElementById('analysisForm');
  if (form) {
    const storageKey = 'lagerhaltungsdaten.analysisSettings.v2';
    const legacyStorageKey = 'lagerhaltungsdaten.analysisSettings.v1';
    const fields = {
      months_average: document.getElementById('monthsAverage'),
      xyz_months: document.getElementById('xyzMonths'),
      analysis_start_date: document.getElementById('analysisStartDate'),
      analysis_end_date: document.getElementById('analysisEndDate')
    };
    const analysisInput = document.getElementById('analysisFile');
    const currentInput = document.getElementById('currentFiles');
    const errorBox = document.getElementById('clientError');
    const statusBox = document.getElementById('clientStatus');
    const calculationFieldset = form.querySelector('.analysis-settings');
    const submitButtons = [...form.querySelectorAll('.form-actions button[type="submit"]')];
    const maxSingleFileBytes = 4_430_000;
    const maxRequestBytes = 4_430_000;

    let preparedToken = null;
    let preparedSignature = '';
    let preparedRange = null;

    const prepareWrap = document.createElement('div');
    prepareWrap.className = 'form-actions prepare-actions';
    const prepareButton = document.createElement('button');
    prepareButton.type = 'button';
    prepareButton.id = 'prepareFiles';
    prepareButton.textContent = 'Dateien einlesen';
    prepareWrap.appendChild(prepareButton);
    calculationFieldset.parentNode.insertBefore(prepareWrap, calculationFieldset);

    const saveSettings = () => {
      try {
        const values = {};
        Object.entries(fields).forEach(([key, element]) => { values[key] = element.value; });
        localStorage.setItem(storageKey, JSON.stringify(values));
      } catch (_) {}
    };

    const setBusy = busy => {
      prepareButton.disabled = busy;
      submitButtons.forEach(button => { button.disabled = busy || !preparedToken; });
      form.setAttribute('aria-busy', busy ? 'true' : 'false');
    };

    const setPrepared = prepared => {
      calculationFieldset.disabled = !prepared;
      submitButtons.forEach(button => { button.disabled = !prepared; });
    };

    const showStatus = message => {
      statusBox.hidden = false;
      statusBox.textContent = message;
      errorBox.hidden = true;
    };

    const showError = message => {
      errorBox.hidden = false;
      errorBox.textContent = message;
      statusBox.hidden = true;
    };

    const appendSettings = data => {
      Object.entries(fields).forEach(([key, element]) => data.append(key, element.value));
    };

    const responseError = async response => {
      const contentType = response.headers.get('content-type') || '';
      if (contentType.includes('application/json')) {
        const payload = await response.json().catch(() => ({}));
        return payload.error || `Anfrage fehlgeschlagen (${response.status}).`;
      }
      const text = await response.text().catch(() => '');
      return text || `Anfrage fehlgeschlagen (${response.status}).`;
    };

    const postJson = async (url, data) => {
      const response = await fetch(url, { method: 'POST', body: data, credentials: 'same-origin' });
      if (!response.ok) throw new Error(await responseError(response));
      return response.json();
    };

    const downloadFilename = response => {
      const disposition = response.headers.get('content-disposition') || '';
      const utf8 = disposition.match(/filename\*=UTF-8''([^;]+)/i);
      if (utf8) return decodeURIComponent(utf8[1]);
      const plain = disposition.match(/filename="?([^";]+)"?/i);
      return plain ? plain[1] : 'Lagerhaltungsanalyse.xlsx';
    };

    const formatSize = bytes => `${(bytes / 1_000_000).toFixed(2)} MB`;

    const fileSignature = () => {
      const analysisFile = analysisInput.files[0];
      const currentFiles = [...currentInput.files];
      return [analysisFile, ...currentFiles]
        .filter(Boolean)
        .map(file => `${file.name}:${file.size}:${file.lastModified}`)
        .join('|');
    };

    const selectedFileSummary = () => {
      const analysisFile = analysisInput.files[0];
      const currentFiles = [...currentInput.files];
      if (!analysisFile) return '';
      const currentSize = currentFiles.reduce((sum, file) => sum + file.size, 0);
      return `Analyse-Datei ${formatSize(analysisFile.size)}${currentFiles.length ? ` · ${currentFiles.length} IST-Datei(en) zusammen ${formatSize(currentSize)}` : ''}`;
    };

    const invalidatePreparedData = () => {
      preparedToken = null;
      preparedSignature = '';
      preparedRange = null;
      setPrepared(false);
      const summary = selectedFileSummary();
      if (summary) {
        showStatus(`${summary}. Bitte «Dateien einlesen» wählen. Danach können Zeitraum und Berechnungslogik eingestellt werden.`);
      }
    };

    if (form.dataset.settingsSubmitted !== 'true') {
      try {
        const savedText = localStorage.getItem(storageKey) || localStorage.getItem(legacyStorageKey) || '{}';
        const saved = JSON.parse(savedText);
        Object.entries(fields).forEach(([key, element]) => {
          if (saved[key] !== undefined && saved[key] !== null) element.value = saved[key];
        });
      } catch (_) {}
    } else {
      saveSettings();
    }
    Object.values(fields).forEach(element => element.addEventListener('change', saveSettings));
    analysisInput.addEventListener('change', invalidatePreparedData);
    currentInput.addEventListener('change', invalidatePreparedData);
    setPrepared(false);

    prepareButton.addEventListener('click', async () => {
      const analysisFile = analysisInput.files[0];
      const currentFiles = [...currentInput.files];
      const allFiles = analysisFile ? [analysisFile, ...currentFiles] : currentFiles;

      if (!analysisFile) {
        showError('Bitte die Analyse-Arbeitsmappe auswählen.');
        return;
      }

      const oversized = allFiles.find(file => file.size > maxSingleFileBytes);
      if (oversized) {
        showError(`${oversized.name} hat ${formatSize(oversized.size)}. Die Webversion kann wegen des Vercel-Limits maximal ca. 4,43 MB pro Einzeldatei verarbeiten.`);
        return;
      }

      setBusy(true);
      try {
        showStatus(`1. Analyse-Arbeitsmappe (${formatSize(analysisFile.size)}) wird eingelesen …`);
        const preparation = new FormData();
        preparation.append('analysis_file', analysisFile);
        const prepared = await postJson('/api/prepare-analysis', preparation);
        let token = prepared.token;

        for (let index = 0; index < currentFiles.length; index += 1) {
          const currentFile = currentFiles[index];
          if (currentFile.size + token.length > maxRequestBytes) {
            throw new Error(`${currentFile.name} kann nicht zusammen mit dem bereits vorbereiteten Analysestatus übertragen werden. Bitte diese IST-Datei verkleinern oder die lokale Version verwenden.`);
          }
          showStatus(`2. Lagerhaltungsdaten ${index + 1} von ${currentFiles.length} (${formatSize(currentFile.size)}) werden eingelesen …`);
          const currentData = new FormData();
          currentData.append('analysis_token', token);
          currentData.append('current_file', currentFile);
          ({ token } = await postJson('/api/add-current', currentData));
        }

        preparedToken = token;
        preparedSignature = fileSignature();
        preparedRange = {
          start: prepared.data_start,
          end: prepared.data_end,
          rows: prepared.sales_rows
        };
        setPrepared(true);

        const rangeText = preparedRange.start && preparedRange.end
          ? ` Datenabdeckung der Artikelposten: ${preparedRange.start.split('-').reverse().join('.')} bis ${preparedRange.end.split('-').reverse().join('.')} (${preparedRange.rows} eingelesene Zeilen).`
          : '';
        showStatus(`Dateien vollständig eingelesen.${rangeText} Jetzt Start-/Enddatum, Durchschnittsmonate und XYZ-Monate festlegen und danach die Analyse starten.`);
      } catch (error) {
        preparedToken = null;
        preparedSignature = '';
        preparedRange = null;
        setPrepared(false);
        showError(error instanceof Error ? error.message : 'Die Dateien konnten nicht eingelesen werden.');
      } finally {
        setBusy(false);
      }
    });

    form.addEventListener('submit', async event => {
      event.preventDefault();
      saveSettings();

      if (!preparedToken || preparedSignature !== fileSignature()) {
        showError('Bitte zuerst die ausgewählten Dateien mit «Dateien einlesen» vorbereiten. Danach können die Berechnungsparameter geändert werden.');
        return;
      }

      if (!form.checkValidity()) {
        form.reportValidity();
        return;
      }

      const outputMode = event.submitter?.value || 'view';
      setBusy(true);
      try {
        showStatus(outputMode === 'download' ? 'Analyse wird berechnet und XLSX erstellt …' : 'Analyse wird mit den aktuell eingestellten Parametern berechnet …');
        const finalData = new FormData();
        finalData.append('analysis_token', preparedToken);
        finalData.append('output_mode', outputMode);
        appendSettings(finalData);
        const response = await fetch('/api/finalize-analysis', {
          method: 'POST',
          body: finalData,
          credentials: 'same-origin'
        });
        if (!response.ok) throw new Error(await responseError(response));

        if (outputMode === 'download') {
          const blob = await response.blob();
          const objectUrl = URL.createObjectURL(blob);
          const link = document.createElement('a');
          link.href = objectUrl;
          link.download = downloadFilename(response);
          document.body.appendChild(link);
          link.click();
          link.remove();
          URL.revokeObjectURL(objectUrl);
          showStatus('XLSX wurde erstellt. Die vorbereiteten Dateien bleiben aktiv; Parameter können geändert und erneut berechnet werden.');
          return;
        }

        const html = await response.text();
        document.open();
        document.write(html);
        document.close();
      } catch (error) {
        showError(error instanceof Error ? error.message : 'Die Analyse konnte nicht abgeschlossen werden.');
      } finally {
        setBusy(false);
      }
    });
  }

  const table = document.getElementById('resultsTable');
  if (!table) return;
  const search = document.getElementById('search');
  const abc = document.getElementById('abc');
  const xyz = document.getElementById('xyz');
  const status = document.getElementById('status');
  const count = document.getElementById('visibleCount');
  const rows = [...table.tBodies[0].rows];
  const apply = () => {
    const term = search.value.trim().toLowerCase();
    let visible = 0;
    rows.forEach(row => {
      const show = (!term || row.dataset.search.includes(term))
        && (!abc.value || row.dataset.abc === abc.value)
        && (!xyz.value || row.dataset.xyz === xyz.value)
        && (!status.value || row.dataset.status === status.value);
      row.hidden = !show;
      if (show) visible++;
    });
    count.textContent = `${visible} von ${rows.length} geladenen Artikeln angezeigt`;
  };
  [search, abc, xyz, status].forEach(element => element.addEventListener('input', apply));
  document.getElementById('resetFilters').addEventListener('click', () => {
    search.value = '';
    abc.value = '';
    xyz.value = '';
    status.value = '';
    apply();
  });
  apply();
})();
