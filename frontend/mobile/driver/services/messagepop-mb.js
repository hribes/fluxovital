document.getElementById("btnCancelar").addEventListener("click", function() {
  // Fecha o modal principal
  const modalPrincipal = bootstrap.Modal.getInstance(document.getElementById("meuModal"));
  modalPrincipal.hide();

  // Abre o modal de sucesso
  const modalSucesso = new bootstrap.Modal(document.getElementById("modalSucesso"));
  modalSucesso.show();

  // Fecha automaticamente depois de 1,5 segundos e redireciona
  setTimeout(() => {
    modalSucesso.hide();
    window.location.href = "../pages/home-paciente.html"; // coloque aqui o caminho da sua página inicial
  }, 1500);
});

document.getElementById("btnChamar").addEventListener("click", function() {
  // Fecha o modal principal
  const modalPrincipal = bootstrap.Modal.getInstance(document.getElementById("meuModal2"));
  modalPrincipal.hide();

});
