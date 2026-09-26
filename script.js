document.getElementById('clickBtn').addEventListener('click', function () {
  document.getElementById('message').textContent = 'JavaScript کارها می‌کند!';
});

const faqButtons = document.querySelectorAll('.faq-question');

faqButtons.forEach(function (button) {
  button.addEventListener('click', function () {
    const answer = button.nextElementSibling;
    answer.classList.toggle('open');
  });
});
