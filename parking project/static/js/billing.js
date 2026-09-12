// billing.js - Checkout modal, payment processor, receipt print

function showReceipt(exitResponse) {
  const v = exitResponse.vehicle;
  const bill = exitResponse.bill;
  const payment = exitResponse.payment;

  document.getElementById('rc-plate').textContent = v.vehicle_number;
  document.getElementById('rc-slot').textContent = v.slot_number || '--';
  document.getElementById('rc-entry').textContent = new Date(v.entry_time + 'Z').toLocaleString();
  document.getElementById('rc-exit').textContent = new Date(v.exit_time + 'Z').toLocaleString();
  document.getElementById('rc-duration').textContent = bill.duration.formatted;
  document.getElementById('rc-base').textContent = fmtMoney(bill.breakdown.base_rate);
  document.getElementById('rc-extra').textContent =
    `${bill.breakdown.extra_hours_charged} hr(s) @ ${fmtMoney(bill.breakdown.hourly_rate)}/hr`;
  document.getElementById('rc-total').textContent = fmtMoney(bill.amount);
  document.getElementById('rc-mode').textContent = payment.payment_mode;
  document.getElementById('rc-txn').textContent = payment.transaction_id;

  const modalEl = document.getElementById('receiptModal');
  const modal = new bootstrap.Modal(modalEl);
  modal.show();
}

function printReceipt() {
  window.print();
}
