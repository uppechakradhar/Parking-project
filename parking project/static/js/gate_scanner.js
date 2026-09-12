// gate_scanner.js - Entry/Exit video feed handler, ANPR trigger, gate controls

function initGateScanner(mode) {
  // mode = 'entry' or 'exit'
  const startBtn = document.getElementById(`btn-start-${mode}-cam`);
  const stopBtn = document.getElementById(`btn-stop-${mode}-cam`);
  const feedImg = document.getElementById(`${mode}-video-feed`);
  const placeholder = document.getElementById(`${mode}-feed-placeholder`);
  const scanBtn = document.getElementById(`btn-scan-${mode}`);

  if (startBtn) {
    startBtn.addEventListener('click', () => {
      feedImg.src = `/video_feed/${mode}?source=0&t=${Date.now()}`;
      feedImg.style.display = 'block';
      placeholder.style.display = 'none';
    });
  }
  if (stopBtn) {
    stopBtn.addEventListener('click', () => {
      feedImg.src = '';
      feedImg.style.display = 'none';
      placeholder.style.display = 'flex';
    });
  }

  if (scanBtn) {
    scanBtn.addEventListener('click', () => {
      if (mode === 'entry') processEntry();
      else processExit();
    });
  }
}

function setGateOpen(mode, isOpen) {
  const statusEl = document.getElementById(`${mode}-gate-status`);
  const barrierEl = document.getElementById(`${mode}-gate-barrier`);
  if (isOpen) {
    statusEl.textContent = 'GATE OPEN';
    statusEl.classList.remove('gate-closed');
    statusEl.classList.add('gate-open');
    barrierEl.classList.add('open');
    setTimeout(() => {
      statusEl.textContent = 'GATE CLOSED';
      statusEl.classList.remove('gate-open');
      statusEl.classList.add('gate-closed');
      barrierEl.classList.remove('open');
    }, 4000);
  }
}

function buildEntryFormData() {
  const fd = new FormData();
  const fileInput = document.getElementById('entry-file-input');
  const manualPlate = document.getElementById('entry-manual-plate').value.trim();
  const vehicleType = document.getElementById('entry-vehicle-type').value;

  if (fileInput && fileInput.files.length > 0) {
    fd.append('media', fileInput.files[0]);
  }
  if (manualPlate) fd.append('plate_number', manualPlate);
  fd.append('vehicle_type', vehicleType);
  return fd;
}

async function processEntry() {
  const fd = buildEntryFormData();
  try {
    const res = await fetch('/api/entry/process', { method: 'POST', body: fd });
    const data = await res.json();

    const plateDisplay = document.getElementById('entry-plate-display');
    const confBadge = document.getElementById('entry-confidence-badge');

    if (data.success) {
      plateDisplay.textContent = data.vehicle.vehicle_number;
      confBadge.textContent = `Confidence: ${data.confidence.toFixed(0)}%`;
      confBadge.className = 'badge bg-success mt-2';
      showToast(`Entry recorded: ${data.vehicle.vehicle_number} → Slot ${data.slot.slot_number}`, 'success');
      setGateOpen('entry', true);
    } else {
      confBadge.textContent = 'Confidence: --';
      confBadge.className = 'badge bg-danger mt-2';
      showToast(data.message || 'Entry failed', 'error');
    }
  } catch (e) {
    showToast('Network error while processing entry', 'error');
    console.error(e);
  }
}

function buildExitFormData() {
  const fd = new FormData();
  const fileInput = document.getElementById('exit-file-input');
  const manualPlate = document.getElementById('exit-manual-plate').value.trim();
  const paymentMode = document.getElementById('exit-payment-mode').value;

  if (fileInput && fileInput.files.length > 0) {
    fd.append('media', fileInput.files[0]);
  }
  if (manualPlate) fd.append('plate_number', manualPlate);
  fd.append('payment_mode', paymentMode);
  return fd;
}

async function processExit() {
  const fd = buildExitFormData();
  try {
    const res = await fetch('/api/exit/process', { method: 'POST', body: fd });
    const data = await res.json();

    const plateDisplay = document.getElementById('exit-plate-display');
    const confBadge = document.getElementById('exit-confidence-badge');

    if (data.success) {
      plateDisplay.textContent = data.vehicle.vehicle_number;
      confBadge.textContent = `Confidence: ${data.confidence.toFixed(0)}%`;
      confBadge.className = 'badge bg-success mt-2';
      showToast(`Exit processed: ${data.vehicle.vehicle_number} — ${fmtMoney(data.bill.amount)}`, 'success');
      setGateOpen('exit', true);
      showReceipt(data);
    } else {
      confBadge.textContent = 'Confidence: --';
      confBadge.className = 'badge bg-danger mt-2';
      showToast(data.message || 'Exit failed', 'error');
    }
  } catch (e) {
    showToast('Network error while processing exit', 'error');
    console.error(e);
  }
}
