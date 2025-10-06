// Auth UI
async function refreshAuthUI() {
  try {
    const r = await fetch('/scanner/api/me', { cache: 'no-store', credentials: 'same-origin' });
    const j = await r.json();
    const userEl = document.getElementById('auth-user');
    const loginBtn = document.getElementById('auth-btn');
    const logoutBtn = document.getElementById('logout-btn');

    if (j && j.authenticated) {
      userEl.textContent = (j.user && (j.user.email || j.user.username)) || 'Signed in';
      userEl.classList.remove('hidden');
      loginBtn.classList.add('hidden');
      logoutBtn.classList.remove('hidden');
    } else {
      userEl.classList.add('hidden');
      loginBtn.classList.remove('hidden');
      logoutBtn.classList.add('hidden');
    }
  } catch { }
}

// Hamburger Menu
function initMenu() {
    console.log("initMenu called");
    const hamburgerBtn = document.getElementById('hamburger-btn');
    const mobileMenu = document.getElementById('mobile-menu');
    console.log("hamburgerBtn:", hamburgerBtn);
    console.log("mobileMenu:", mobileMenu);

    if (hamburgerBtn && mobileMenu) {
        hamburgerBtn.addEventListener('click', () => {
            console.log("Hamburger button clicked");
            if (mobileMenu.classList.contains('hidden')) {
                mobileMenu.classList.remove('hidden');
            } else {
                mobileMenu.classList.add('hidden');
            }
        });
    }
}

// Transcript Editing
function enableEdit(id) {
  document.getElementById(`pre-${id}`).classList.add("hidden");
  document.getElementById(`edit-${id}`).classList.remove("hidden");
  document.getElementById(`save-${id}`).classList.remove("hidden");
  document.getElementById(`cancel-${id}`).classList.remove("hidden");
  document.getElementById(`msg-${id}`).classList.add("hidden");
}

function cancelEdit(id) {
  const pre = document.getElementById(`pre-${id}`);
  const edit = document.getElementById(`edit-${id}`);
  edit.value = pre.innerText.trim();
  edit.classList.add("hidden");
pre.classList.remove("hidden");
  document.getElementById(`save-${id}`).classList.add("hidden");
  document.getElementById(`cancel-${id}`).classList.add("hidden");
}

async function submitEdit(filename, feed, id) {
  const edited = document.getElementById(`edit-${id}`).value;
  const resp = await fetch("/scanner/submit_edit", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ filename, feed, transcript: edited })
  });

  if (resp.ok) {
    document.getElementById(`save-${id}`).classList.add("hidden");
    document.getElementById(`cancel-${id}`).classList.add("hidden");
    document.getElementById(`edit-${id}`).classList.add("hidden");
    document.getElementById(`pre-${id}`).classList.remove("hidden");
    document.getElementById(`msg-${id}`).classList.remove("hidden");
  } else {
    alert("Submission failed.");
  }
}

// Infinite Scroll
let loading = false;
let page = 1;
let moreCalls = true;
let totalCalls = 0;

function isNearBottom() {
  return (window.innerHeight + window.scrollY) >= (document.body.offsetHeight - 200);
}

async function loadMoreCalls(url) {
  if (loading || !moreCalls || !isNearBottom()) return;
  loading = true;
  const loadingIndicator = document.getElementById('loading-indicator');
  if(loadingIndicator) loadingIndicator.classList.remove('hidden');
  page += 1;

  const resp = await fetch(`${url}?page=${page}`, { headers: { Accept: 'application/json' } });
  if (resp.ok) {
    const data = await resp.json();
    if (data.calls && data.calls.length > 0) {
      const container = document.getElementById('calls-container');
      if (page === 2) { // First time loading more calls
        const initialCalls = document.querySelectorAll('.call-entry');
        totalCalls = initialCalls.length;
      }
      data.calls.forEach((call, i) => {
        const index = totalCalls++; // Use the running total for a guaranteed unique index
        const div = document.createElement('div');
        div.className = 'bg-gray-800/50 backdrop-blur-sm p-6 rounded-2xl shadow-lg ring-1 ring-white/10 call-entry';
        div.innerHTML = `
          <div class="text-sm text-gray-400 mb-2">${call.timestamp_human} | ${call.feed}</div>
          <audio class="w-full mb-4" controls src="${call.path}"></audio>
          <div class="space-y-4">
            ${call.metadata && call.metadata.enhanced_transcript ? `
              <div>
                <div class="text-purple-400 font-semibold text-sm mb-2">✨ Enhanced Transcript</div>
                <pre class="whitespace-pre-wrap bg-purple-900/50 p-3 rounded-md text-sm text-purple-100 overflow-auto">${call.metadata.enhanced_transcript}</pre>
              </div>
            ` : ''}
            ${call.metadata && call.metadata.edited_transcript ? `
              <div>
                <div class="text-green-400 font-semibold text-sm mb-2">✅ Edited Transcript</div>
                <pre class="whitespace-pre-wrap bg-green-800/50 p-3 rounded-md text-sm text-green-100 overflow-auto">${call.metadata.edited_transcript}</pre>
              </div>
            ` : call.edit_pending ? `
              <div>
                <div class="text-yellow-400 font-semibold text-sm mb-2">✏️ Edit Pending</div>
                <pre class="whitespace-pre-wrap bg-yellow-800/50 p-3 rounded-md text-sm text-yellow-100 overflow-auto">${call.edited_transcript}</pre>
              </div>
            ` : ''}
            <div>
              <div class="text-gray-400 font-semibold text-sm mb-2">🎧 Original Transcript</div>
              <pre id="pre-${index}" class="whitespace-pre-wrap bg-gray-700/50 p-3 rounded-md text-sm text-gray-200 overflow-auto">${call.transcript}</pre>
              <textarea id="edit-${index}" class="w-full bg-gray-800 text-sm p-3 rounded-md text-white border border-gray-600 hidden">${call.transcript}</textarea>
              <div class="flex gap-2 mt-2">
                <button onclick="enableEdit(${index})" class="text-yellow-400 hover:underline text-sm">Edit</button>
                <button onclick="submitEdit('${call.file}', '${call.feed}', ${index})" id="save-${index}" class="hidden text-green-400 hover:underline text-sm">Submit</button>
                <button onclick="cancelEdit(${index})" id="cancel-${index}" class="hidden text-red-400 hover:underline text-sm">Cancel</button>
              </div>
              <div id="msg-${index}" class="text-green-400 text-sm hidden">✔️ Thank you for your submission!</div>
            </div>
          </div>
        `;
        container.appendChild(div);
      });
      const totalCallsEl = document.getElementById('total-calls');
      if (totalCallsEl) {
        totalCallsEl.textContent = `Total calls: ${totalCalls}`;
      }
    } else {
      moreCalls = false;
    }
  }
  loading = false;
  if(loadingIndicator) loadingIndicator.classList.add('hidden');
}


// Initialize
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible') refreshAuthUI();
});
window.addEventListener('load', () => {
    refreshAuthUI();
    initMenu();
});