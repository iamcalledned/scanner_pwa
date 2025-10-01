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

// Push Subscription UI
(function() {
  const vapidUrl = '/scanner/push/vapid_public';
  const subscribeUrl = '/scanner/push/subscribe';
  const unsubscribeUrl = '/scanner/push/unsubscribe';

  const stateEl = document.getElementById('notif-state');
  const toggleBtn = document.getElementById('notif-toggle');
  const unsubBtn = document.getElementById('notif-unsub');
  const msgEl = document.getElementById('notif-msg');

  function setState(s) { if(stateEl) stateEl.textContent = s; }
  function setMsg(s) { if(msgEl) msgEl.textContent = s; }

  async function urlBase64ToUint8Array(base64String) {
    const padding = '='.repeat((4 - base64String.length % 4) % 4);
    const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
    const rawData = window.atob(base64);
    const outputArray = new Uint8Array(rawData.length);
    for (let i = 0; i < rawData.length; ++i) {
      outputArray[i] = rawData.charCodeAt(i);
    }
    return outputArray;
  }

  async function getVapidKey() {
    const r = await fetch(vapidUrl);
    if (!r.ok) throw new Error('no vapid key');
    return (await r.text()).trim();
  }

  async function subscribePush() {
    if (!('serviceWorker' in navigator)) { setMsg('No service worker'); return; }
    try {
      const reg = await navigator.serviceWorker.ready;
      const vapid = await getVapidKey();
      console.log('vapid key fetched (len):', vapid && vapid.length);
      if (!vapid || typeof vapid !== 'string') throw new Error('invalid vapid key');
      const key = await urlBase64ToUint8Array(vapid);
      console.log('applicationServerKey ready, length', key.length);
      const sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: key
      });
      // send the serializable subscription data
      const j = await fetch(subscribeUrl, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(sub.toJSON())});
      if (j.ok) {
        setMsg('Subscribed for notifications');
        setState('enabled');
        toggleBtn.classList.add('hidden');
        unsubBtn.classList.remove('hidden');
      } else {
        setMsg('Subscription save failed');
      }
    } catch (e) {
      console.error('subscribePush error', e);
      setMsg('Subscribe error: ' + (e && e.message));
    }
  }

  async function unsubscribePush() {
    try {
      const reg = await navigator.serviceWorker.ready;
      const sub = await reg.pushManager.getSubscription();
      if (sub) {
        await fetch(unsubscribeUrl, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({endpoint: sub.endpoint})});
        await sub.unsubscribe();
        setMsg('Unsubscribed');
        setState('disabled');
        toggleBtn.classList.remove('hidden');
        unsubBtn.classList.add('hidden');
      }
    } catch (e) { setMsg('Unsubscribe error'); }
  }

    if(toggleBtn) {
        toggleBtn.addEventListener('click', async () => {
          if (Notification.permission === 'default') {
            const p = await Notification.requestPermission();
            if (p !== 'granted') { setMsg('Notification permission denied'); return; }
          }
          await subscribePush();
        });
    }

    if(unsubBtn) {
        unsubBtn.addEventListener('click', async () => {
          await unsubscribePush();
        });
    }


  // initialize UI based on current subscription
  (async function initPushUI() {
    if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
      setState('unsupported');
      if(toggleBtn) toggleBtn.disabled = true;
      return;
    }
    try {
      const reg = await navigator.serviceWorker.ready;
      const sub = await reg.pushManager.getSubscription();
      if (sub) {
        setState('enabled');
        if(toggleBtn) toggleBtn.classList.add('hidden');
        if(unsubBtn) unsubBtn.classList.remove('hidden');
      } else {
        setState(Notification.permission === 'granted' ? 'disabled' : 'prompt');
      }
    } catch (e) { setState('error'); }
  })();

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