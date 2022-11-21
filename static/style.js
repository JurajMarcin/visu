document.body.classList.remove("nojs");
document.querySelector("#nav-button").addEventListener("click", () => {
    document.querySelector(".nav").classList.toggle("nav--open");
});
