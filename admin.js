const adminStatus = document.getElementById('adminStatus');
const messagesList = document.getElementById('messagesList');

function showUnauthorized() {
  adminStatus.className = 'admin-status error';
  adminStatus.textContent = 'دسترسی مجاز نیست';
}

function addField(card, label, value) {
  const p = document.createElement('p');
  const strong = document.createElement('strong');
  strong.textContent = label + ': ';
  p.appendChild(strong);
  // textContent (not innerHTML) so submitted text can't inject HTML/scripts
  p.appendChild(document.createTextNode(value || ''));
  card.appendChild(p);
}

async function loadMessages(token) {
  adminStatus.textContent = 'در حال دریافت پیام‌ها...';

  try {
    const response = await fetch('https://kajdom110.pythonanywhere.com/api/messages', {
      headers: { 'X-Admin-Token': token }
    });

    if (response.status === 401) {
      showUnauthorized();
      return;
    }

    if (!response.ok) {
      throw new Error('Request failed: ' + response.status);
    }

    const messages = await response.json();

    if (messages.length === 0) {
      adminStatus.textContent = 'هنوز درخواستی ثبت نشده است.';
      return;
    }

    adminStatus.textContent = '';
    messages.forEach(function (item) {
      const card = document.createElement('div');
      card.className = 'message-card';
      addField(card, 'نام', item.name);
      addField(card, 'ایمیل', item.email);
      addField(card, 'پیام', item.message);
      messagesList.appendChild(card);
    });
  } catch (error) {
    adminStatus.className = 'admin-status error';
    adminStatus.textContent = 'دریافت پیام‌ها انجام نشد. لطفاً دوباره تلاش کنید.';
  }
}

const loginForm = document.getElementById('loginForm');
const loginStatus = document.getElementById('loginStatus');
const loginButton = loginForm.querySelector('button');

// Token from /api/login; kept only in memory, so a page reload asks to log in again
let adminToken = null;

function showLoginError(text) {
  loginStatus.className = 'form-status error';
  loginStatus.textContent = text;
}

loginForm.addEventListener('submit', async function (event) {
  event.preventDefault();

  const username = document.getElementById('username').value;
  const password = document.getElementById('password').value;

  loginStatus.className = 'form-status';
  loginStatus.textContent = 'در حال ورود...';
  loginButton.disabled = true;

  try {
    const response = await fetch('https://kajdom110.pythonanywhere.com/api/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: username, password: password })
    });

    if (response.status === 401) {
      showLoginError('نام‌کاربری یا رمز اشتباه است');
      return;
    }

    if (!response.ok) {
      throw new Error('Request failed: ' + response.status);
    }

    const data = await response.json();
    adminToken = data.token;

    // Not loginForm.hidden: .contact-form's display: flex would override it
    loginForm.style.display = 'none';
    loadMessages(adminToken);
  } catch (error) {
    showLoginError('ورود انجام نشد. لطفاً دوباره تلاش کنید.');
  } finally {
    loginButton.disabled = false;
  }
});
