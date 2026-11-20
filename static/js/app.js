
document.addEventListener('DOMContentLoaded', () => {
  // flash auto hide
  setTimeout(()=>{ document.querySelectorAll('.flash').forEach(el=>el.style.opacity='0') }, 4000);
  
  // payment toggle
  const payOpts = document.querySelectorAll('input[name="pago"]');
  const cardFields = document.getElementById('card-fields');
  if(payOpts.length && cardFields){
    payOpts.forEach(r=> r.addEventListener('change', ()=>{
      cardFields.style.display = r.value.includes('Tarjeta') && r.checked ? 'block' : 'none';
    }));
  }

  document.querySelectorAll('[data-countdown]').forEach(timer => {
    const deadline = performance.now() + Number(timer.dataset.countdown) * 1000;
    let reloading = false;
    const updateTimer = () => {
      const remaining = Math.max(0, Math.ceil((deadline - performance.now()) / 1000));
      const minutes = Math.floor(remaining / 60).toString().padStart(2, '0');
      const seconds = (remaining % 60).toString().padStart(2, '0');
      timer.textContent = `${minutes}:${seconds}`;
      if (remaining === 0 && !reloading) {
        reloading = true;
        window.setTimeout(() => window.location.reload(), 1000);
      }
    };
    updateTimer();
    window.setInterval(updateTimer, 1000);
  });
});
