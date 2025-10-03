// Service Worker Registration
if ('serviceWorker' in navigator) {
  window.addEventListener('load', function() {
    navigator.serviceWorker.register('/scanner/sw.js').then(function(registration) {
      console.log('ServiceWorker registration successful with scope: ', registration.scope);

      // If there's an updated worker waiting, prompt user
      if (registration.waiting) {
        showUpdateToast(registration);
      }

      registration.addEventListener('updatefound', () => {
        const installing = registration.installing;
        installing.addEventListener('statechange', () => {
          if (installing.state === 'installed') {
            if (registration.waiting) {
              showUpdateToast(registration);
            }
          }
        });
      });

    }, function(err) {
      console.log('ServiceWorker registration failed: ', err);
    });
  });
}

// Update Toast
function showUpdateToast(registration) {
  const toast = document.getElementById('update-toast');
  const btn = document.getElementById('update-reload');
  toast.classList.remove('hidden');
  btn.onclick = () => {
    if (!registration || !registration.waiting) return;
    registration.waiting.postMessage({ type: 'SKIP_WAITING' });
    // after skipWaiting, refresh to let the new worker take control
    registration.waiting.addEventListener('statechange', (e) => {
      if (e.target.state === 'activated') {
        window.location.reload();
      }
    });
  };
}

// PWA Install Prompt
let deferredPrompt;
const installBtn = document.getElementById('pwa-install-btn');

window.addEventListener('beforeinstallprompt', (e) => {
  // Prevent the mini-infobar from appearing on mobile
  e.preventDefault();
  deferredPrompt = e;
  // Show the install button
  if(installBtn) installBtn.classList.remove('hidden');
});

if(installBtn) {
    installBtn.addEventListener('click', async () => {
      if (!deferredPrompt) return;
      installBtn.disabled = true;
      deferredPrompt.prompt();
      const choiceResult = await deferredPrompt.userChoice;
      if (choiceResult.outcome === 'accepted') {
        console.log('User accepted the A2HS prompt');
      } else {
        console.log('User dismissed the A2HS prompt');
      }
      deferredPrompt = null;
      installBtn.classList.add('hidden');
      installBtn.disabled = false;
    });
}


window.addEventListener('appinstalled', () => {
    if(installBtn) installBtn.classList.add('hidden');
  deferredPrompt = null;
});

// PWA Diagnostics
(async function pwaDiagnostics() {
  try {
    console.group('PWA Diagnostics');

    // Manifest
    try {
      const mfResp = await fetch('/scanner/manifest.json', {cache: 'no-cache'});
      console.log('manifest fetch status:', mfResp.status, mfResp.headers.get('content-type'));
      if (mfResp.ok) {
        const mf = await mfResp.json();
        console.log('manifest JSON:', mf);
        if (Array.isArray(mf.icons)) {
          for (const ic of mf.icons) {
            try {
              const iconUrl = new URL(ic.src, location.href).href;
              const h = await fetch(iconUrl, {method: 'HEAD', cache: 'no-cache'});
              console.log('icon HEAD', iconUrl, h.status, h.headers.get('content-type'));
              // attempt to load image to check actual pixel size
              await new Promise((res, rej) => {
                const img = new Image();
                img.onload = () => { console.log('icon size', iconUrl, img.width, img.height); res(); };
                img.onerror = (e) => { console.warn('icon load failed', iconUrl, e); res(); };
                img.src = iconUrl + '?_=' + Date.now();
              });
            } catch (e) {
              console.warn('icon check failed', ic, e);
            }
          }
        }
      }
    } catch (e) {
      console.warn('manifest fetch failed', e);
    }

    // Service worker status
    if ('serviceWorker' in navigator) {
      try {
        const regs = await navigator.serviceWorker.getRegistrations();
        console.log('service worker registrations:', regs.map(r => ({scope: r.scope, active: !!r.active, waiting: !!r.waiting, installing: !!r.installing})));
        console.log('navigator.serviceWorker.controller:', !!navigator.serviceWorker.controller);
      } catch (e) {
        console.warn('SW regs failed', e);
      }
    }

    // Display-mode & installed checks
    console.log('display-mode:', window.matchMedia('(display-mode: standalone)').matches ? 'standalone' : 'browser');
    if (navigator.getInstalledRelatedApps) {
      try { const apps = await navigator.getInstalledRelatedApps(); console.log('related apps:', apps); } catch(e){console.warn('related apps failed', e);} 
    }

    console.groupEnd();
  } catch (err) {
    console.error('PWA diagnostic failed', err);
  }
})();

// Client Heartbeat
(function() {
  const HB_URL = '/scanner/_heartbeat';
  const HB_INTERVAL = 30 * 1000;
  let clientId = localStorage.getItem('scanner_client_id');
  if (!clientId) {
    clientId = '';
  }

  async function sendHeartbeat() {
    try {
      const res = await fetch(HB_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ client_id: clientId, page: location.pathname })
      });
      const j = await res.json();
      if (j && j.client_id) {
        clientId = j.client_id;
        localStorage.setItem('scanner_client_id', clientId);
      }
    } catch (e) {
      // ignore network errors
    }
  }

  // Send immediately and then every interval
  sendHeartbeat();
  setInterval(sendHeartbeat, HB_INTERVAL);

  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') sendHeartbeat();
  });
})();



// Status Refresh
async function refreshStatus() {
  try {
    const r = await fetch('/scanner/api/status');
    const j = await r.json();
    const fdFreq = document.getElementById('fd-freq');
    const pdFreq = document.getElementById('pd-freq');
    const sigStrength = document.getElementById('sig-strength');

    if(fdFreq) fdFreq.textContent = j.FD?.frequency || '--';
    if(pdFreq) pdFreq.textContent = j.PD?.frequency || '--';
    if(sigStrength) sigStrength.textContent = j.PD?.strength || '--';
  } catch {}
}
setInterval(refreshStatus, 5000);
refreshStatus();