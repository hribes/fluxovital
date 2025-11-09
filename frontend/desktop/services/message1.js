
document.getElementById("btnCadastrar").addEventListener("click", function() {
  // Fecha o modal principal
  const modalPrincipal = bootstrap.Modal.getInstance(document.getElementById("meuModal"));
  modalPrincipal.hide();

  // Abre o modal de sucesso
  const modalSucesso = new bootstrap.Modal(document.getElementById("modalSucesso"));
  modalSucesso.show();

  // Fecha automaticamente depois de 2,5 segundos
  setTimeout(() => {
    modalSucesso.hide();
  }, 1500);
});

