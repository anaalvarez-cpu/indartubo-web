/* Indartubo · JS compartido (sin librerías). */
(function () {
  'use strict';

  // ---------------------------------------------------------------------------
  // Vista local: al abrir los archivos con doble clic (file://) los links "/hierros"
  // no existen como archivo; se pasan a "hierros.html". En el sitio publicado no hace nada.
  // ---------------------------------------------------------------------------
  if (location.protocol === 'file:') {
    document.querySelectorAll('a[href^="/"]').forEach(function (a) {
      var partes = a.getAttribute('href').split('#');
      var archivo = partes[0] === '/' ? 'index.html' : partes[0].slice(1) + '.html';
      a.setAttribute('href', archivo + (partes[1] ? '#' + partes[1] : ''));
    });
  }

  // Cerrar el menú mobile al tocar un link.
  document.querySelectorAll('details.menu-movil a').forEach(function (a) {
    a.addEventListener('click', function () {
      var d = a.closest('details'); if (d) d.removeAttribute('open');
    });
  });

  // ---------------------------------------------------------------------------
  // Desplegable "Productos" (escritorio). Sin JS ya abre con hover y con foco;
  // esto suma clic (aria-expanded), Esc para cerrar y cierre al hacer clic afuera.
  // ---------------------------------------------------------------------------
  document.querySelectorAll('.desplegable').forEach(function (d) {
    var boton = d.querySelector('.desplegable__boton');
    var cerrar = function () { boton.setAttribute('aria-expanded', 'false'); };
    boton.addEventListener('click', function () {
      d.classList.remove('cerrado');
      boton.setAttribute('aria-expanded', boton.getAttribute('aria-expanded') === 'true' ? 'false' : 'true');
    });
    d.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') { cerrar(); d.classList.add('cerrado'); boton.focus(); }
    });
    d.addEventListener('mouseleave', function () { d.classList.remove('cerrado'); });
    d.addEventListener('focusout', function (e) {
      if (!d.contains(e.relatedTarget)) { cerrar(); d.classList.remove('cerrado'); }
    });
    document.addEventListener('click', function (e) { if (!d.contains(e.target)) cerrar(); });
  });

  // ---------------------------------------------------------------------------
  // Aparición suave al entrar en pantalla. Solo se ocultan elementos que están
  // por debajo de la pantalla al cargar: lo visible nunca parpadea y, si este
  // archivo no carga, todo el contenido se ve igual.
  // ---------------------------------------------------------------------------
  // Garantías de visibilidad (nada depende solo del IntersectionObserver):
  //  - sin JS, sin IntersectionObserver o con movimiento reducido: no se oculta nada;
  //  - respaldo por scroll: todo lo que ya entró (o quedó arriba) se muestra igual;
  //  - el mapa no se anima nunca; al imprimir se ve todo (CSS @media print).
  var reducirMovimiento = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (!reducirMovimiento && 'IntersectionObserver' in window) {
    var SELECTOR = '.seccion h2, .seccion__bajada, .tarjeta, .nosotros__grilla > div:first-child, ' +
      '.collage__foto, .collage__dato, .ubicacion__grilla > div:first-child, .diferenciales__lista li, ' +
      '.variedad, .ficha__bloque, .otros > li';
    var pendientes = [];

    var revelar = function (el) {
      var i = pendientes.indexOf(el);
      if (i === -1) return;
      pendientes.splice(i, 1);
      observador.unobserve(el);
      el.classList.add('revelar--visible');
      el.addEventListener('transitionend', function fin(ev) {
        if (ev.propertyName !== 'opacity') return;
        el.classList.remove('revelar', 'revelar--visible');
        el.style.removeProperty('--retraso');
        el.removeEventListener('transitionend', fin);
      });
    };

    var observador = new IntersectionObserver(function (entradas) {
      entradas.forEach(function (en) { if (en.isIntersecting) revelar(en.target); });
    }, { rootMargin: '0px 0px -8% 0px', threshold: 0.1 });

    document.querySelectorAll(SELECTOR).forEach(function (el) {
      if (el.getBoundingClientRect().top < window.innerHeight) return; // ya visible: no se toca
      var hermanos = Array.prototype.indexOf.call(el.parentNode.children, el);
      el.style.setProperty('--retraso', (hermanos % 3) * 90 + 'ms');
      el.classList.add('revelar');
      pendientes.push(el);
      observador.observe(el);
    });

    // Respaldo: al scrollear o cambiar el tamaño, revelar lo que ya está a la vista o por encima.
    var programado = false;
    var revisar = function () {
      programado = false;
      pendientes.slice().forEach(function (el) {
        if (el.getBoundingClientRect().top < window.innerHeight) revelar(el);
      });
      if (!pendientes.length) {
        window.removeEventListener('scroll', alScrollear);
        window.removeEventListener('resize', alScrollear);
      }
    };
    var alScrollear = function () {
      if (!programado) { programado = true; requestAnimationFrame(revisar); }
    };
    window.addEventListener('scroll', alScrollear, { passive: true });
    window.addEventListener('resize', alScrollear);
  }

  // ---------------------------------------------------------------------------
  // Números que cuentan hacia arriba al entrar en pantalla (ej. "50 años").
  // El HTML ya trae el número final: sin JS o con movimiento reducido se ve tal cual.
  // El ancho del número está reservado en CSS (min-width + tabular-nums): no corre nada.
  // ---------------------------------------------------------------------------
  if (!reducirMovimiento && 'IntersectionObserver' in window) {
    var observadorNumeros = new IntersectionObserver(function (entradas) {
      entradas.forEach(function (en) {
        if (!en.isIntersecting) return;
        var el = en.target, fin = parseInt(el.getAttribute('data-contar-hasta'), 10), inicio = null;
        observadorNumeros.unobserve(el);
        function paso(t) {
          if (inicio === null) inicio = t;
          var avance = Math.min(1, (t - inicio) / 1400);
          el.textContent = Math.round(fin * (1 - Math.pow(1 - avance, 3)));
          if (avance < 1) requestAnimationFrame(paso);
        }
        requestAnimationFrame(paso);
      });
    }, { threshold: 0.6 });
    document.querySelectorAll('[data-contar-hasta]').forEach(function (el) {
      if (el.getBoundingClientRect().top < window.innerHeight) return; // ya visible: queda el número final
      el.textContent = '0';
      observadorNumeros.observe(el);
    });
  }

  var form = document.getElementById('formulario-presupuesto');
  if (!form) return;

  var selectProducto = form.querySelector('[name="producto"]');
  var boton = form.querySelector('[type="submit"]');
  var estado = form.querySelector('.formulario__estado');
  var textoBoton = boton.textContent;
  var TIEMPO_MAXIMO = 20000; // ms

  // ---------------------------------------------------------------------------
  // Botones "Cotizar [producto]": preseleccionan el producto y bajan al formulario
  // (el scroll lo hace el propio link #presupuesto, con scroll suave por CSS).
  // ---------------------------------------------------------------------------
  document.querySelectorAll('[data-producto]').forEach(function (link) {
    link.addEventListener('click', function () {
      var producto = link.getAttribute('data-producto');
      if (selectProducto && producto) {
        selectProducto.value = producto;
        var campo = selectProducto.closest('.campo');
        campo.classList.add('campo--resaltado');
        setTimeout(function () { campo.classList.remove('campo--resaltado'); }, 1800);
      }
      // Foco en el formulario sin abrir el teclado del celular.
      setTimeout(function () { form.focus({ preventScroll: true }); }, 400);
    });
  });

  // ---------------------------------------------------------------------------
  // Tarjetas de variedad (páginas de producto): el link baja al formulario y acá se
  // agrega "Consulta por: [variedad]" al campo Consulta SIN borrar lo ya escrito.
  // Si ya hay una línea "Consulta por: …" al principio, se suma la variedad a esa línea.
  // ---------------------------------------------------------------------------
  var consulta = form.querySelector('[name="consulta"]');
  document.querySelectorAll('[data-variedad]').forEach(function (link) {
    link.addEventListener('click', function () {
      if (!consulta) return;
      var variedad = link.getAttribute('data-variedad');
      var texto = consulta.value;
      var m = texto.match(/^Consulta por: ([^\n]*)/);
      if (m) {
        var lista = m[1].split(', ').filter(Boolean);
        if (lista.indexOf(variedad) === -1) lista.push(variedad);
        consulta.value = 'Consulta por: ' + lista.join(', ') + texto.slice(m[0].length);
      } else {
        consulta.value = 'Consulta por: ' + variedad + (texto ? '\n' + texto : '\n');
      }
      var campo = consulta.closest('.campo');
      campo.classList.add('campo--resaltado');
      setTimeout(function () { campo.classList.remove('campo--resaltado'); }, 1800);
      setTimeout(function () { form.focus({ preventScroll: true }); }, 400);
    });
  });

  // ---------------------------------------------------------------------------
  // Validación
  // ---------------------------------------------------------------------------
  var reglas = {
    nombre: function (v) { return v.trim().length >= 2 || 'Escribí tu nombre.'; },
    email: function (v) {
      if (!v.trim()) return 'Escribí tu mail.';
      return /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(v.trim()) || 'Revisá el mail: parece incompleto.';
    },
    telefono: function (v) {
      if (!v.trim()) return 'Escribí tu teléfono.';
      return v.replace(/\D/g, '').length >= 8 || 'Revisá el teléfono: con código de área, al menos 8 números.';
    }
  };

  function marcar(campo, mensaje) {
    var error = document.getElementById(campo.id + '-error');
    if (mensaje) {
      campo.setAttribute('aria-invalid', 'true');
      if (error) { error.textContent = mensaje; error.hidden = false; }
    } else {
      campo.removeAttribute('aria-invalid');
      if (error) { error.textContent = ''; error.hidden = true; }
    }
  }

  function validarCampo(campo) {
    var regla = reglas[campo.name];
    if (!regla) return true;
    var r = regla(campo.value);
    marcar(campo, r === true ? '' : r);
    return r === true;
  }

  Object.keys(reglas).forEach(function (nombre) {
    var campo = form.elements[nombre];
    if (!campo) return;
    campo.addEventListener('blur', function () { if (campo.value) validarCampo(campo); });
    campo.addEventListener('input', function () {
      if (campo.getAttribute('aria-invalid') === 'true') validarCampo(campo);
    });
  });

  function mostrarEstado(tipo, html) {
    estado.className = 'formulario__estado formulario__estado--' + tipo;
    estado.innerHTML = html;
    estado.hidden = false;
  }

  function escapar(t) {
    return t.replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  var MENSAJE_ERROR = 'No pudimos enviar tu consulta. Revisá tu conexión y probá de nuevo. ' +
    'Si sigue sin funcionar, escribinos a <a href="mailto:ventas@indartubo.com.ar">ventas@indartubo.com.ar</a>.';

  // ---------------------------------------------------------------------------
  // Envío: espera la respuesta. "Gracias" y dataLayer SOLO si el servidor confirma.
  // Si falla, no se borra nada de lo que escribió la persona.
  // ---------------------------------------------------------------------------
  form.addEventListener('submit', function (e) {
    e.preventDefault();
    estado.hidden = true;

    // Versión de prueba (construir.py --preview): no se envía nada ni se dispara el evento.
    if (form.getAttribute('data-prueba') === 'si') {
      mostrarEstado('aviso', '<strong>Esta es una versión de prueba.</strong> El formulario no envía datos. ' +
        'En el sitio publicado, la consulta llega a ventas@indartubo.com.ar.');
      estado.setAttribute('tabindex', '-1');
      estado.focus();
      return;
    }

    var primeroInvalido = null;
    Object.keys(reglas).forEach(function (nombre) {
      var campo = form.elements[nombre];
      if (campo && !validarCampo(campo) && !primeroInvalido) primeroInvalido = campo;
    });
    if (primeroInvalido) { primeroInvalido.focus(); return; }

    var endpoint = form.getAttribute('action');
    if (!endpoint) {
      console.error('Formulario sin destino: completar "form_endpoint" en fuente/config.json y correr construir.py');
      mostrarEstado('error', MENSAJE_ERROR);
      return;
    }

    var datos = new FormData(form);
    datos.append('pagina', location.pathname);
    var producto = selectProducto && selectProducto.value ? selectProducto.value : 'Sin especificar';

    boton.disabled = true;
    boton.textContent = 'Enviando…';
    var control = new AbortController();
    var temporizador = setTimeout(function () { control.abort(); }, TIEMPO_MAXIMO);

    fetch(endpoint, { method: 'POST', body: datos, headers: { 'Accept': 'application/json' }, signal: control.signal })
      .then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        // Si el servidor responde JSON con { ok: false }, también es error.
        return r.text().then(function (t) {
          try { var j = JSON.parse(t); if (j && j.ok === false) throw new Error('ok:false'); } catch (err) {
            if (err.message === 'ok:false') throw err;
          }
        });
      })
      .then(function () {
        var nombre = form.elements.nombre.value.trim().split(' ')[0];
        form.reset();
        mostrarEstado('ok', '<strong>¡Gracias' + (nombre ? ', ' + escapar(nombre) : '') +
          '!</strong> Recibimos tu consulta. Te respondemos a la brevedad.');
        window.dataLayer = window.dataLayer || [];
        window.dataLayer.push({ event: 'indartubo_form_enviado', producto: producto });
      })
      .catch(function (err) {
        console.error('Error al enviar el formulario:', err);
        mostrarEstado('error', MENSAJE_ERROR);
      })
      .then(function () {
        clearTimeout(temporizador);
        boton.disabled = false;
        boton.textContent = textoBoton;
        estado.setAttribute('tabindex', '-1');
        estado.focus();
      });
  });
})();
