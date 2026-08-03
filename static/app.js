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
    const submitButtons = [...form.querySelectorAll('button[type="submit"]')];
    const maxSingleFileBytes = 4_100_000;
    const maxRequestBytes = 4_300_000;

    const saveSettings = () => {
      try {
        const values = {};
        Object.entries(fields).forEach(([key, element]) => { values[key] = element.value; });
        localStorage.setItem(storageKey, JSON.stringify(values));
      } catch (_) {}
    };

    const setBusy = busy => {
      submitButtons.forEach(button => { button.disabled = busy; });
      form.setAttribute('aria-busy', busy ? 'true' : 'false');
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

    form.addEventListener('submit', async event => {
      event.preventDefault();
      saveSettings();

      const analysisFile = analysisInput.files[0];
      const currentFiles = [...currentInput.files];
      const outputMode = event.submitter?.value || 'view';
      const allFiles = analysisFile ? [analysisFile, ...currentFiles] : currentFiles;

      if (!analysisFile) {
        showError('Bitte die Analyse-Arbeitsmappe auswählen.');
        return;
      }
      const oversized = allFiles.find(file => file.size > maxSingleFileBytes);
      if (oversized) {
        showError(`${oversized.name} ist grösser als ca. 4,1 MB. Bitte diese einzelne Datei verkleinern oder die lokale Version verwenden.`);
        return;
      }

      setBusy(true);
      try {
        showStatus('1. Analyse-Arbeitsmappe wird verarbeitet …');
        const preparation = new FormData();
        preparation.append('analysis_file', analysisFile);
        appendSettings(preparation);
        let { token } = await postJson('/api/prepare-analysis', preparation);

        for (let index = 0; index < currentFiles.length; index += 1) {
          const currentFile = currentFiles[index];
          if (currentFile.size + token.length > maxRequestBytes) {
            throw new Error(`${currentFile.name} ist zusammen mit dem temporären Analysestatus zu gross für die Webversion.`);
          }
          showStatus(`2. Lagerhaltungsdaten ${index + 1} von ${currentFiles.length} werden ergänzt …`);
          const currentData = new FormData();
          currentData.append('analysis_token', token);
          currentData.append('current_file', currentFile);
          ({ token } = await postJson('/api/add-current', currentData));
        }

        showStatus(outputMode === 'download' ? '3. XLSX wird erstellt …' : '3. Ergebnisansicht wird erstellt …');
        const finalData = new FormData();
        finalData.append('analysis_token', token);
        finalData.append('output_mode', outputMode);
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
          showStatus('XLSX wurde erstellt. Die ausgewählten Dateien bleiben für eine weitere Analyse erhalten.');
          setBusy(false);
          return;
        }

        const html = await response.text();
        document.open();
        document.write(html);
        document.close();
      } catch (error) {
        showError(error instanceof Error ? error.message : 'Die Analyse konnte nicht abgeschlossen werden.');
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
