// dashboard.js - Real-time slot status, live timers, analytics charts

let occupancyChart = null;
let revenueChart = null;

function slotStatusClass(status) {
  if (status === 'AVAILABLE') return 'slot-available';
  if (status === 'OCCUPIED') return 'slot-occupied';
  return 'slot-reserved';
}

async function refreshSlots() {
  try {
    const res = await fetch('/api/slots');
    const slots = await res.json();
    const grid = document.getElementById('slot-grid');
    grid.innerHTML = '';
    slots.forEach(s => {
      const div = document.createElement('div');
      div.className = `slot-box ${slotStatusClass(s.status)}`;
      let inner = `<div class="slot-number">${s.slot_number}</div>`;
      if (s.vehicle) {
        inner += `<div class="slot-plate">${s.vehicle.vehicle_number}</div>`;
        inner += `<div class="slot-timer" data-entry="${s.vehicle.entry_time}">--:--:--</div>`;
      }
      div.innerHTML = inner;
      grid.appendChild(div);
    });
    tickTimers();
  } catch (e) { console.error('slot refresh failed', e); }
}

function tickTimers() {
  document.querySelectorAll('.slot-timer[data-entry]').forEach(el => {
    const entry = new Date(el.dataset.entry + 'Z');
    const diffSec = Math.max(0, Math.floor((Date.now() - entry.getTime()) / 1000));
    const h = String(Math.floor(diffSec / 3600)).padStart(2, '0');
    const m = String(Math.floor((diffSec % 3600) / 60)).padStart(2, '0');
    const s = String(diffSec % 60).padStart(2, '0');
    el.textContent = `${h}:${m}:${s}`;
  });
}

async function refreshActiveVehicles() {
  try {
    const res = await fetch('/api/vehicles/active');
    const vehicles = await res.json();
    const tbody = document.getElementById('active-vehicles-body');
    tbody.innerHTML = '';
    if (vehicles.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted py-3">No vehicles currently parked</td></tr>';
      return;
    }
    vehicles.forEach(v => {
      tbody.innerHTML += `
        <tr>
          <td class="fw-semibold">${v.vehicle_number}</td>
          <td>${v.vehicle_type}</td>
          <td>${v.slot_number || '--'}</td>
          <td>${new Date(v.entry_time + 'Z').toLocaleTimeString()}</td>
          <td><span class="badge bg-secondary">${v.live_duration}</span></td>
          <td class="text-success fw-semibold">${fmtMoney(v.live_amount)}</td>
        </tr>`;
    });
  } catch (e) { console.error('active vehicles refresh failed', e); }
}

async function refreshAnalytics() {
  try {
    const res = await fetch('/api/analytics');
    const data = await res.json();
    document.getElementById('metric-available').textContent = data.available_slots;
    document.getElementById('metric-occupied').textContent = data.occupied_slots;
    document.getElementById('metric-revenue').textContent = fmtMoney(data.today_revenue);
    document.getElementById('metric-occupancy').textContent = data.occupancy_rate + '%';

    const occCtx = document.getElementById('occupancyChart');
    if (occupancyChart) occupancyChart.destroy();
    occupancyChart = new Chart(occCtx, {
      type: 'doughnut',
      data: {
        labels: ['Occupied', 'Available'],
        datasets: [{ data: [data.occupied_slots, data.available_slots], backgroundColor: ['#dc3545', '#198754'] }]
      },
      options: { plugins: { legend: { labels: { color: '#e8eaed' } } } }
    });

    const revCtx = document.getElementById('revenueChart');
    if (revenueChart) revenueChart.destroy();
    revenueChart = new Chart(revCtx, {
      type: 'line',
      data: {
        labels: data.weekly_revenue.map(w => w.date.slice(5)),
        datasets: [{
          label: 'Revenue',
          data: data.weekly_revenue.map(w => w.revenue),
          borderColor: '#4f9dff',
          backgroundColor: 'rgba(79,157,255,0.2)',
          fill: true, tension: 0.3
        }]
      },
      options: {
        plugins: { legend: { labels: { color: '#e8eaed' } } },
        scales: { x: { ticks: { color: '#aaa' } }, y: { ticks: { color: '#aaa' } } }
      }
    });
  } catch (e) { console.error('analytics refresh failed', e); }
}

function refreshAll() {
  refreshSlots();
  refreshActiveVehicles();
  refreshAnalytics();
}

refreshAll();
setInterval(refreshSlots, 3000);
setInterval(refreshActiveVehicles, 3000);
setInterval(refreshAnalytics, 15000);
setInterval(tickTimers, 1000);
