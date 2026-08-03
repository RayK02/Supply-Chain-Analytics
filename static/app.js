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
    const saveSettings = () => {
      try {
        const values = {};
        Object.entries(fields).forEach(([key, element]) => { values[key] = element.value; });
        localStorage.setItem(storageKey, JSON.stringify(values));
      } catch (_) {}
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

    form.addEventListener('submit', event => {
      saveSettings();
      const files = [
        ...document.getElementById('analysisFile').files,
        ...document.getElementById('currentFiles').files
      ];
      const totalBytes = files.reduce((sum, file) => sum + file.size, 0);
      const errorBox = document.getElementById('clientError');
      if (totalBytes > 3.8 * 1024 * 1024) {
        event.preventDefault();
        errorBox.hidden = false;
        errorBox.textContent = 'Die ausgewählten Dateien sind zusammen zu gross. Bitte unter ca. 3,8 MB bleiben oder die lokale Version verwenden.';
      } else {
        errorBox.hidden = true;
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
