/*
 * Refresco de la ficha mientras la IA redacta (ADR-D7 para noticias, ADR-D8 para normas).
 *
 * La redacción corre en el worker, así que el POST de guardar vuelve al instante y el editor se
 * queda sin saber cuándo terminó. Esto sondea el estado y **recarga la página** en cuanto cambia,
 * de modo que aparecen los campos llenos —o el error con su motivo— sin pulsar nada.
 *
 * Solo se activa si la ficha está en «procesando». En cualquier otro estado no hace ni una
 * petición: no tiene sentido sondear algo que ya terminó.
 *
 * Con corte por número de intentos. Si el contenedor `worker` está caído nadie va a mover ese
 * estado nunca, y un indicador girando para siempre miente más que un aviso que se rinde y lo dice.
 */
(function () {
  "use strict";

  var INTERVALO_MS = 2000;
  var INTENTOS_MAXIMOS = 90; // 3 minutos, holgado para un timeout de 60 s más su reintento

  document.addEventListener("DOMContentLoaded", function () {
    var campo = document.querySelector(".field-ia_badge_ficha");
    if (!campo || campo.textContent.indexOf("Procesando") === -1) {
      return;
    }

    // La URL de la ficha es …/<app>/<modelo>/<pk>/change/ y el prefijo del admin es configurable,
    // así que la base y el pk se derivan de aquí en vez de escribirse a mano. Genérico a
    // propósito: el mismo archivo sirve a noticias y a normas, y el endpoint que consulta también
    // es uno solo. Qué modelos se aceptan lo decide el servidor, no esta expresión.
    var partes = window.location.pathname.match(/^(.*\/[a-z_]+\/[a-z_]+\/)(\d+)\/change\//);
    if (!partes) {
      return;
    }
    var consulta = partes[1] + partes[2] + "/estado-ia/";

    var aviso = document.createElement("p");
    aviso.style.margin = "8px 0 0";
    aviso.style.color = "#1D4ED8";
    aviso.textContent = "Redactando con IA… la página se actualizará sola al terminar.";
    campo.appendChild(aviso);

    var intentos = 0;

    function sondear() {
      intentos += 1;
      if (intentos > INTENTOS_MAXIMOS) {
        aviso.style.color = "#7C2D12";
        aviso.textContent =
          "La redacción sigue sin terminar. Puede que el procesador de tareas esté detenido: " +
          "recarga para comprobarlo, o avisa al administrador de la plataforma.";
        return;
      }

      fetch(consulta, { credentials: "same-origin", headers: { Accept: "application/json" } })
        .then(function (respuesta) {
          if (!respuesta.ok) {
            throw new Error(respuesta.status);
          }
          return respuesta.json();
        })
        .then(function (datos) {
          if (datos.estado === "procesando") {
            window.setTimeout(sondear, INTERVALO_MS);
            return;
          }
          window.location.reload();
        })
        .catch(function () {
          // Un fallo suelto puede ser un despliegue a medias o una sesión que caducó: se reintenta
          // hasta agotar los intentos, y entonces se dice.
          window.setTimeout(sondear, INTERVALO_MS);
        });
    }

    window.setTimeout(sondear, INTERVALO_MS);
  });
})();
