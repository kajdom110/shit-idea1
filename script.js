const faqButtons = document.querySelectorAll('.faq-question');

faqButtons.forEach(function (button) {
  button.addEventListener('click', function () {
    const answer = button.nextElementSibling;
    answer.classList.toggle('open');
  });
});

const servicesList = document.getElementById('services');
const servicesStatus = document.getElementById('servicesStatus');

function createServiceCard(service) {
  const card = document.createElement('div');
  card.className = 'feature';

  // textContent (not innerHTML) so API data can't inject HTML/scripts
  const title = document.createElement('h3');
  title.textContent = service.title || '';
  card.appendChild(title);

  const description = document.createElement('p');
  description.textContent = service.description || '';
  card.appendChild(description);

  return card;
}

async function loadServices() {
  try {
    const response = await fetch('https://kajdom110.pythonanywhere.com/api/services');

    if (!response.ok) {
      throw new Error('Request failed: ' + response.status);
    }

    const services = await response.json();

    if (services.length === 0) {
      servicesStatus.textContent = 'در حال حاضر خدمتی برای نمایش وجود ندارد.';
      return;
    }

    servicesStatus.textContent = '';
    servicesStatus.hidden = true;
    services.forEach(function (service) {
      servicesList.appendChild(createServiceCard(service));
    });
  } catch (error) {
    servicesStatus.className = 'services-status error';
    servicesStatus.textContent = 'دریافت خدمات انجام نشد. لطفاً بعداً دوباره تلاش کنید.';
  }
}

loadServices();
