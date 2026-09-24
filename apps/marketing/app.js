// Smart Spectator — Apple HIG Clean Interaction Script

document.addEventListener('DOMContentLoaded', () => {
  const qrModal = document.getElementById('qr-modal');
  const qrToggleBtn = document.getElementById('qr-toggle-btn');
  const qrCloseBtn = document.getElementById('qr-close-btn');

  // QR Modal toggle
  if (qrToggleBtn && qrModal && qrCloseBtn) {
    qrToggleBtn.addEventListener('click', () => {
      qrModal.classList.add('open');
      qrModal.setAttribute('aria-hidden', 'false');
    });

    const closeModal = () => {
      qrModal.classList.remove('open');
      qrModal.setAttribute('aria-hidden', 'true');
    };

    qrCloseBtn.addEventListener('click', closeModal);

    qrModal.addEventListener('click', (e) => {
      if (e.target === qrModal) {
        closeModal();
      }
    });

    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && qrModal.classList.contains('open')) {
        closeModal();
      }
    });
  }
});
