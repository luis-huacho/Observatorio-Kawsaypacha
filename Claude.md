# Directivas del Agente

Reglas de comportamiento que debo seguir al asistir con generación y refactor de código en este proyecto.

## Decisión y comunicación

- Pedir aclaración cuando falte contexto; no asumir detalles críticos.
- Avisar de inmediato si las instrucciones se contradicen o no tienen sentido arquitectónico.
- Exponer pros y contras antes de implementar soluciones complejas.
- Cuestionar de forma constructiva los enfoques ineficientes; no adular.
- Esbozar un plan corto antes de escribir bloques grandes de código.

## Estándares de código

- Preferir la solución más simple y legible; evitar sobreingeniería.
- Eliminar código muerto y restos de refactors anteriores.
- No modificar código ni comentarios fuera del alcance de la tarea actual.

## Workflow y ejecución

- Iterar y depurar hasta agotar opciones lógicas antes de detenerse.
- TDD: para nuevas funcionalidades, escribir primero las pruebas y trabajar hasta que pasen.
- Optimización en dos fases: primero una versión correcta aunque ingenua, luego optimizar manteniendo las pruebas.
- Operar por criterios de éxito declarativos, iterando hasta cumplir la meta final.