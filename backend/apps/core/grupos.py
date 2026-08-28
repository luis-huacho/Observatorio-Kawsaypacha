"""Nombres de los grupos de trabajo (spec 03).

Existen como constantes porque el seed que los crea y el admin que decide qué acciones ofrecer
tienen que coincidir exactamente. La primera versión del aviso por correo buscaba «Publicadores»
mientras el seed creaba «Publicador», así que los correos no llegaban a nadie — y sin
destinatarios la tarea termina bien, de modo que el fallo era invisible.

Aquí vivía `GRUPOS_REVISORES`, la lista de quién recibía el aviso de «espera revisión». Se retiró
con ADR-P3 junto al propio paso de revisión: los dos correos que quedan van al autor.
"""

EDITOR = "Editor"
PUBLICADOR = "Publicador"
ADMINISTRADOR = "Administrador"

TODOS = [EDITOR, PUBLICADOR, ADMINISTRADOR]
