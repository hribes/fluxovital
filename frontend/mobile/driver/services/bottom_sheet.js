const sheet = document.getElementById('bottomSheet');
let startY, currentY, isDragging = false;

// Início do toque
sheet.addEventListener('touchstart', (e) => {
  startY = e.touches[0].clientY;
  isDragging = true;
});

// Movimento
sheet.addEventListener('touchmove', (e) => {
  if (!isDragging) return;
  currentY = e.touches[0].clientY;
  const diff = currentY - startY;

  // Arrasta só pra baixo
  if (diff > 0) {
    sheet.style.transform = `translateY(${diff}px)`;
  }
});

// Fim do toque
sheet.addEventListener('touchend', () => {
  isDragging = false;
  const diff = currentY - startY;

  // Se arrastar mais de 150px, fecha o painel
  if (diff > 150) {
    sheet.classList.remove('active');
    sheet.style.transform = 'translateY(calc(100% - 40px))';
  } else {
    sheet.classList.add('active');
    sheet.style.transform = 'translateY(0)';
  }
});

// Clique no risquinho
sheet.querySelector('.drag-handle').addEventListener('click', () => {
  sheet.classList.toggle('active');
  if (sheet.classList.contains('active')) {
    sheet.style.transform = 'translateY(0)';
  } else {
    sheet.style.transform = 'translateY(calc(100% - 40px))';
  }
});
