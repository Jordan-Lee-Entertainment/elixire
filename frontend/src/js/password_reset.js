window.addEventListener("DOMContentLoaded", function() {
  const resetBtn = document.getElementById("change-btn");
  const password = document.getElementById("password");
  const passwordValidity = document.getElementById("password-validity");
  const resetForm = document.getElementById("reset-form");
  resetForm.addEventListener("submit", function(ev) {
    ev.preventDefault();
    ev.stopPropagation();
    return false;
  });
  resetBtn.addEventListener("click", async function() {
    try {
      await client.confirmPasswordReset(
        window.location.hash.substring(1),
        password.value
      );
      window.location = "/";
    } catch (err) {
      if (err.response.body.message == "Invalid token.")
        passwordValidity.innerText = "Invalid/Expired Reset Link!";
      else passwordValidity.innerText = "Invalid Password";
      password.setCustomValidity("Invalid");
      resetForm.classList = "was-validated needs-validation";
    }
  });
});
