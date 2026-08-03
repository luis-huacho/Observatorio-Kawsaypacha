"""Nombres de los grupos de trabajo (spec 03).

Existen como constantes porque se usan en tres sitios que tienen que coincidir exactamente: el
seed que los crea, el aviso por correo que busca a quién escribir, y el admin que decide qué
acciones ofrecer. La primera versión del aviso buscaba «Publicadores» mientras el seed creaba
«Publicador», así que los correos de «espera revisión» no llegaban a nadie — y sin destinatarios
la tarea termina bien, de modo que el fallo era invisible.
"""

EDITOR = "Editor"
PUBLICADOR = "Publicador"
ADMINISTRADOR = "Administrador"

#: Quién recibe el aviso de «espera revisión».
GRUPOS_REVISORES = [PUBLICADOR, ADMINISTRADOR]

TODOS = [EDITOR, PUBLICADOR, ADMINISTRADOR]
