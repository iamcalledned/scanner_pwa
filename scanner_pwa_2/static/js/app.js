// Auth UI
async function refreshAuthUI() {
  try {
    const r = await fetch('/scanner/api/me', { cache: 'no-store', credentials: 'same-origin' });
    const j = await r.json();
    const btn = document.getElementById('auth-btn');
    const menu = document.getElementById('auth-menu');
    const user = document.getElementById('auth-user');
    if (j && j.authenticated) {
      btn.textContent = '👤 Account';
      btn.href = '#';
      btn.onclick = (e) => { e.preventDefault(); menu.classList.toggle('hidden'); };
      user.textContent = (j.user && (j.user.email || j.user.username)) || 'Signed in';
    } else {
      btn.textContent = '🔒 Login';
      btn.href = '/scanner/login';
      btn.onclick = null;
      menu.classList.add('hidden');
    }
  } catch { }
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
      data.calls.forEach((call, i) => {
        const index = page * 10 + i + 1;  // ensure loop index is unique
        const div = document.createElement('div');
        div.className = 'mb-6 p-4 rounded-xl bg-gray-800 shadow-md call-entry';
        div.innerHTML = `
          <div class="text-sm text-gray-400 mb-1">${call.timestamp_human} ${call.feed || ''}</div>
          <audio class="w-full mb-2" controls src="${call.path}"></audio>
          <div class="space-y-2">
            ${call.edit_pending ? `
              <div class="text-yellow-400 text-sm">✏️ Edit Pending</div>
              <pre class="whitespace-pre-wrap bg-yellow-800 p-3 rounded-md text-sm text-yellow-100 overflow-auto">${call.edited_transcript}</pre>
              <div class="text-sm text-gray-400">Original Transcript:</div>
              <pre class="whitespace-pre-wrap bg-gray-700 p-3 rounded-md text-sm text-gray-300 overflow-auto">${call.transcript}</pre>
            ` : `
              <pre id="pre-${index}" class="whitespace-pre-wrap bg-gray-700 p-3 rounded-md text-sm text-gray-200 overflow-auto">${call.transcript}</pre>
              <textarea id="edit-${index}" class="w-full bg-gray-800 text-sm p-3 rounded-md text-white border border-gray-600 hidden">${call.transcript}</textarea>
              <div class="flex gap-2">
                <button onclick="enableEdit(${index})" class="text-yellow-400 hover:underline text-sm">Edit</button>
                <button onclick="submitEdit('${call.file}', '${call.feed}', ${index})" id="save-${index}" class="hidden text-green-400 hover:underline text-sm">Submit</button>
                <button onclick="cancelEdit(${index})" id="cancel-${index}" class="hidden text-red-400 hover:underline text-sm">Cancel</button>
              </div>
              <div id="msg-${index}" class="text-green-400 text-sm hidden">✔️ Thank you for your submission!</div>
            `}
          </div>
        `;
        container.appendChild(div);
      });
    } else {
      moreCalls = false;
    }
  }
  loading = false;
  if(loadingIndicator) loadingIndicator.classList.add('hidden');
}

// Initialize Auth UI
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible') refreshAuthUI();
});
window.addEventListener('load', refreshAuthUI);