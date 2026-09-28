const contactForm = document.getElementById('contactForm');
const formStatus = document.getElementById('formStatus');

contactForm.addEventListener('submit', async function (event) {
  event.preventDefault();

  const button = contactForm.querySelector('button');
  const data = {
    name: contactForm.name.value.trim(),
    email: contactForm.email.value.trim(),
    message: contactForm.message.value.trim()
  };

  button.disabled = true;
  formStatus.className = 'form-status';
  formStatus.textContent = 'در حال ارسال...';

  try {
    const response = await fetch('https://kajdom110.pythonanywhere.com/api/contact', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });

    if (!response.ok) {
      throw new Error('Request failed: ' + response.status);
    }

    formStatus.className = 'form-status success';
    formStatus.textContent = 'درخواست شما ثبت شد، به‌زودی باهاتون تماس می‌گیریم.';
    contactForm.reset();
  } catch (error) {
    formStatus.className = 'form-status error';
    formStatus.textContent = 'متأسفانه ارسال پیام انجام نشد. لطفاً دوباره تلاش کنید.';
  } finally {
    button.disabled = false;
  }
});
