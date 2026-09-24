// Smart Spectator — Interactive Marketing App Logic

document.addEventListener('DOMContentLoaded', () => {
  // Elements
  const toast = document.getElementById('toast');
  const qrModal = document.getElementById('qr-modal');
  const qrModalBtn = document.getElementById('qr-modal-btn');
  const qrCloseBtn = document.getElementById('qr-close-btn');
  const iosNotifyBtn = document.getElementById('ios-notify-btn');
  const simulateTriggerBtn = document.getElementById('simulate-trigger-btn');
  const activeBBox = document.getElementById('active-bbox');
  const boxLabel = document.getElementById('box-label');
  const logEntries = document.getElementById('log-entries');
  const fpsCounter = document.getElementById('fps-counter');

  // Helper: Show toast notification
  let toastTimer = null;
  function showToast(message) {
    if (!toast) return;
    toast.textContent = message;
    toast.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
      toast.classList.remove('show');
    }, 2800);
  }

  // Copy buttons
  document.querySelectorAll('.copy-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const url = btn.getAttribute('data-url');
      if (url) {
        try {
          await navigator.clipboard.writeText(url);
          showToast(`Copied: ${url}`);
        } catch (e) {
          showToast('Failed to copy to clipboard');
        }
      }
    });
  });

  // QR Modal handling
  if (qrModalBtn && qrModal && qrCloseBtn) {
    qrModalBtn.addEventListener('click', () => {
      qrModal.classList.add('open');
    });

    qrCloseBtn.addEventListener('click', () => {
      qrModal.classList.remove('open');
    });

    qrModal.addEventListener('click', (e) => {
      if (e.target === qrModal) {
        qrModal.classList.remove('open');
      }
    });
  }

  // iOS Notify button
  if (iosNotifyBtn) {
    iosNotifyBtn.addEventListener('click', () => {
      showToast('iOS TestFlight build is scheduled for release soon!');
    });
  }

  // Subtle real-time FPS jitter to simulate live camera stream
  if (fpsCounter) {
    setInterval(() => {
      const fps = (29.8 + Math.random() * 0.4).toFixed(1);
      fpsCounter.textContent = `${fps} FPS`;
    }, 1200);
  }

  // Simulated detection sequences
  const detections = [
    { label: 'Person 98.7%', left: '32%', top: '40px', width: '140px', height: '130px', cls: 'person (0.98)' },
    { label: 'Pet 94.2%', left: '60%', top: '90px', width: '90px', height: '80px', cls: 'cat/dog (0.94)' },
    { label: 'Package 91.5%', left: '15%', top: '110px', width: '70px', height: '65px', cls: 'package (0.91)' },
    { label: 'Motion 89.0%', left: '45%', top: '60px', width: '160px', height: '110px', cls: 'motion_zone (0.89)' },
  ];

  let detIndex = 0;
  let currentSeq = 1050;

  function triggerDetection() {
    detIndex = (detIndex + 1) % detections.length;
    const current = detections[detIndex];

    if (activeBBox && boxLabel) {
      activeBBox.style.left = current.left;
      activeBBox.style.top = current.top;
      activeBBox.style.width = current.width;
      activeBBox.style.height = current.height;
      boxLabel.textContent = current.label;
    }

    currentSeq++;
    const now = new Date();
    const timeStr = [
      String(now.getHours()).padStart(2, '0'),
      String(now.getMinutes()).padStart(2, '0'),
      String(now.getSeconds()).padStart(2, '0')
    ].join(':');

    if (logEntries) {
      const newLine = document.createElement('div');
      newLine.className = 'log-line';
      newLine.innerHTML = `<span class="log-ts">${timeStr}</span> <span class="log-badge badge-ai">AI</span> Edge inference: <span class="hl">${current.cls}</span> detected. seq=#${currentSeq}`;
      
      logEntries.appendChild(newLine);
      if (logEntries.children.length > 5) {
        logEntries.removeChild(logEntries.children[0]);
      }
    }
  }

  if (simulateTriggerBtn) {
    simulateTriggerBtn.addEventListener('click', () => {
      triggerDetection();
      showToast('Simulated edge detection event triggered');
    });
  }
});
