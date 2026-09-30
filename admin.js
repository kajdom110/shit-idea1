const API_BASE = 'https://kajdom110.pythonanywhere.com/api';

const adminPanel = document.getElementById('adminPanel');
const adminStatus = document.getElementById('adminStatus');
const messagesList = document.getElementById('messagesList');

// Token from /api/login; kept only in memory, so a page reload asks to log in again
let adminToken = null;

function setStatus(element, baseClass, text, isError) {
  element.className = isError ? baseClass + ' error' : baseClass;
  element.textContent = text;
}

function showUnauthorized() {
  setStatus(adminStatus, 'admin-status', 'دسترسی مجاز نیست', true);
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
  setStatus(adminStatus, 'admin-status', 'در حال دریافت پیام‌ها...', false);

  try {
    const response = await fetch(API_BASE + '/messages', {
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

    // Logged out (or in again) while this request was running
    if (token !== adminToken) {
      return;
    }

    // Cleared here, not before the fetch, so overlapping loads can't duplicate cards
    messagesList.replaceChildren();

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
    setStatus(adminStatus, 'admin-status', 'دریافت پیام‌ها انجام نشد. لطفاً دوباره تلاش کنید.', true);
  }
}

// ---------- Services ----------

const servicesStatus = document.getElementById('servicesStatus');
const servicesList = document.getElementById('servicesList');
const serviceForm = document.getElementById('serviceForm');
const serviceFormStatus = document.getElementById('serviceFormStatus');
const serviceFormButton = serviceForm.querySelector('button');

function adminRequest(path, method, body) {
  const headers = { 'X-Admin-Token': adminToken };
  if (body) {
    headers['Content-Type'] = 'application/json';
  }
  return fetch(API_BASE + path, {
    method: method,
    headers: headers,
    body: body ? JSON.stringify(body) : undefined
  });
}

// The backend's own error text (e.g. empty title), or a fallback
async function errorText(response, fallback) {
  if (response.status === 401) {
    return 'دسترسی مجاز نیست';
  }
  try {
    const data = await response.json();
    return data.error || fallback;
  } catch (error) {
    return fallback;
  }
}

function createButton(text, extraClass) {
  const button = document.createElement('button');
  button.type = 'button';
  button.className = extraClass ? 'admin-button ' + extraClass : 'admin-button';
  button.textContent = text;
  return button;
}

function createStatus() {
  const status = document.createElement('p');
  status.className = 'form-status';
  status.setAttribute('role', 'status');
  return status;
}

function showServiceView(card, service) {
  card.replaceChildren();
  addField(card, 'عنوان', service.title);
  addField(card, 'توضیح', service.description);

  const editButton = createButton('ویرایش');
  const deleteButton = createButton('حذف', 'danger');
  const status = createStatus();

  editButton.addEventListener('click', function () {
    showServiceEditor(card, service);
  });
  deleteButton.addEventListener('click', function () {
    deleteService(service, deleteButton, status);
  });

  const actions = document.createElement('div');
  actions.className = 'service-actions';
  actions.append(editButton, deleteButton);
  card.append(actions, status);
}

function showServiceEditor(card, service) {
  card.replaceChildren();

  const titleLabel = document.createElement('label');
  titleLabel.className = 'service-edit-field';
  titleLabel.textContent = 'عنوان';
  const titleInput = document.createElement('input');
  titleInput.type = 'text';
  titleInput.value = service.title;
  titleLabel.appendChild(titleInput);

  const descriptionLabel = document.createElement('label');
  descriptionLabel.className = 'service-edit-field';
  descriptionLabel.textContent = 'توضیح';
  const descriptionInput = document.createElement('textarea');
  descriptionInput.rows = 3;
  descriptionInput.value = service.description;
  descriptionLabel.appendChild(descriptionInput);

  const saveButton = createButton('ذخیره');
  const cancelButton = createButton('انصراف', 'secondary');
  const status = createStatus();

  saveButton.addEventListener('click', function () {
    updateService(service, titleInput.value, descriptionInput.value, saveButton, status);
  });
  cancelButton.addEventListener('click', function () {
    showServiceView(card, service);
  });

  const actions = document.createElement('div');
  actions.className = 'service-actions';
  actions.append(saveButton, cancelButton);

  card.append(titleLabel, descriptionLabel, actions, status);
  titleInput.focus();
}

async function loadServices() {
  setStatus(servicesStatus, 'admin-status', 'در حال دریافت خدمات...', false);

  try {
    // Reading services is public, so no token header here
    const response = await fetch(API_BASE + '/services');

    if (!response.ok) {
      throw new Error('Request failed: ' + response.status);
    }

    const services = await response.json();

    // Logged out while this request was running
    if (!adminToken) {
      return;
    }

    servicesList.replaceChildren();

    if (services.length === 0) {
      servicesStatus.textContent = 'هنوز خدمتی ثبت نشده است.';
      return;
    }

    servicesStatus.textContent = '';
    services.forEach(function (service) {
      const card = document.createElement('div');
      card.className = 'message-card';
      showServiceView(card, service);
      servicesList.appendChild(card);
    });
  } catch (error) {
    setStatus(servicesStatus, 'admin-status', 'دریافت خدمات انجام نشد. لطفاً دوباره تلاش کنید.', true);
  }
}

async function updateService(service, title, description, saveButton, status) {
  setStatus(status, 'form-status', 'در حال ذخیره...', false);
  saveButton.disabled = true;

  try {
    const response = await adminRequest('/services/' + service.id, 'PUT', {
      title: title,
      description: description
    });

    if (!response.ok) {
      setStatus(status, 'form-status', await errorText(response, 'ذخیره انجام نشد.'), true);
      return;
    }

    loadServices();
  } catch (error) {
    setStatus(status, 'form-status', 'ذخیره انجام نشد. لطفاً دوباره تلاش کنید.', true);
  } finally {
    saveButton.disabled = false;
  }
}

async function deleteService(service, deleteButton, status) {
  if (!confirm('خدمت «' + service.title + '» حذف شود؟')) {
    return;
  }

  setStatus(status, 'form-status', 'در حال حذف...', false);
  deleteButton.disabled = true;

  try {
    const response = await adminRequest('/services/' + service.id, 'DELETE');

    if (!response.ok) {
      setStatus(status, 'form-status', await errorText(response, 'حذف انجام نشد.'), true);
      return;
    }

    loadServices();
  } catch (error) {
    setStatus(status, 'form-status', 'حذف انجام نشد. لطفاً دوباره تلاش کنید.', true);
  } finally {
    deleteButton.disabled = false;
  }
}

serviceForm.addEventListener('submit', async function (event) {
  event.preventDefault();

  const title = document.getElementById('serviceTitle').value;
  const description = document.getElementById('serviceDescription').value;

  setStatus(serviceFormStatus, 'form-status', 'در حال ثبت...', false);
  serviceFormButton.disabled = true;

  try {
    const response = await adminRequest('/services', 'POST', {
      title: title,
      description: description
    });

    if (!response.ok) {
      setStatus(serviceFormStatus, 'form-status', await errorText(response, 'ثبت انجام نشد.'), true);
      return;
    }

    serviceForm.reset();
    setStatus(serviceFormStatus, 'form-status success', 'خدمت اضافه شد.', false);
    loadServices();
  } catch (error) {
    setStatus(serviceFormStatus, 'form-status', 'ثبت انجام نشد. لطفاً دوباره تلاش کنید.', true);
  } finally {
    serviceFormButton.disabled = false;
  }
});

// ---------- Login / logout ----------

const loginForm = document.getElementById('loginForm');
const loginStatus = document.getElementById('loginStatus');
const loginButton = loginForm.querySelector('button');
const logoutButton = document.getElementById('logoutButton');

function showLoginError(text) {
  setStatus(loginStatus, 'form-status', text, true);
}

loginForm.addEventListener('submit', async function (event) {
  event.preventDefault();

  const username = document.getElementById('username').value;
  const password = document.getElementById('password').value;

  setStatus(loginStatus, 'form-status', 'در حال ورود...', false);
  loginButton.disabled = true;

  try {
    const response = await fetch(API_BASE + '/login', {
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
    adminPanel.hidden = false;
    loadMessages(adminToken);
    loadServices();
  } catch (error) {
    showLoginError('ورود انجام نشد. لطفاً دوباره تلاش کنید.');
  } finally {
    loginButton.disabled = false;
  }
});

logoutButton.addEventListener('click', function () {
  adminToken = null;

  // Empty the lists too, so admin data doesn't stay in the page after logout
  adminPanel.hidden = true;
  messagesList.replaceChildren();
  servicesList.replaceChildren();
  setStatus(adminStatus, 'admin-status', '', false);
  setStatus(servicesStatus, 'admin-status', '', false);
  serviceForm.reset();
  setStatus(serviceFormStatus, 'form-status', '', false);

  loginForm.reset();
  setStatus(loginStatus, 'form-status', '', false);
  loginForm.style.display = '';
});
