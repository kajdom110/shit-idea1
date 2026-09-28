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

const password = prompt('رمز را وارد کنید:');

// The backend checks the token; skip the request only if nothing was entered
if (password) {
  loadMessages(password);
} else {
  showUnauthorized();
}
