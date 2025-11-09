document.addEventListener("DOMContentLoaded", function () {
  const selectUsuario = document.querySelector(".select-usuario");
  const cpfInput = document.querySelector(".cpf-paciente");
  const emailInput = document.querySelector(".email-usuario");
  const senhaInput = document.querySelector(".senha-usuario");

  function atualizarCampos() {
    const valor = selectUsuario.value;

    cpfInput.style.display = "none";
    emailInput.style.display = "none";
    senhaInput.style.display = "none";

    if (valor === "2") { // Paciente
      cpfInput.style.display = "block";
    } else if (valor === "1" || valor === "3") { // Atendente ou Motorista
      emailInput.style.display = "block";
      senhaInput.style.display = "block";
    }
  }

  selectUsuario.addEventListener("change", atualizarCampos);

  atualizarCampos();
});
