"""Contenido inicial de la guía de emergencia.

Los textos de las emergencias son los que Oscar escribió en la app; se suman las líneas de
emergencia de Colombia y lo legal sobre personas desaparecidas. Lo carga
`scripts/seed/guia_emergencia.py` cuando la tabla está vacía; después lo edita el super admin.
"""

GUIAS_INICIALES: list[dict] = [
    {
        "categoria": "sismo",
        "titulo": "Terremoto",
        "pasos": [
            "Mantén la calma. No corras ni uses ascensores.",
            "Agáchate, cúbrete bajo una mesa resistente y sujétate.",
            "Aléjate de ventanas, espejos y objetos que puedan caer.",
            "Si estás afuera, aléjate de edificios, postes y cables.",
            "Al terminar, sal con cuidado, revisa si hay heridos y ten presente que pueden venir réplicas.",
        ],
    },
    {
        "categoria": "inundacion",
        "titulo": "Inundación",
        "pasos": [
            "Sube a un lugar alto sin esperar a que el agua suba.",
            "No cruces corrientes de agua a pie ni en vehículo.",
            "Si puedes hacerlo con seguridad, desconecta la electricidad y el gas.",
            "Aléjate de postes, cables caídos y alcantarillas.",
            "Sigue las indicaciones de las autoridades y no regreses hasta que lo autoricen.",
        ],
    },
    {
        "categoria": "incendio",
        "titulo": "Incendio",
        "pasos": [
            "Da la alarma y llama a emergencias.",
            "Si hay humo, agáchate y cúbrete nariz y boca con un paño, mejor si está húmedo.",
            "Antes de abrir una puerta, tócala con el dorso de la mano. Si está caliente, no la abras.",
            "Sal por la ruta de evacuación y no uses ascensores.",
            "Una vez afuera, no regreses por ningún motivo.",
        ],
    },
    {
        "categoria": "accidente",
        "titulo": "Accidente",
        "pasos": [
            "Detente en un lugar seguro y enciende las luces de emergencia.",
            "Llama a emergencias e indica tu ubicación exacta.",
            "No muevas a los heridos, salvo que haya peligro inmediato.",
            "Señaliza el lugar para evitar otro choque.",
            "Quédate en el sitio hasta que llegue la ayuda.",
        ],
    },
    {
        "categoria": "deslizamiento",
        "titulo": "Deslizamiento",
        "pasos": [
            "Si notas grietas, árboles inclinados o ruido de rocas, aléjate de inmediato.",
            "Dirígete a terreno firme y alto, lejos de la ladera.",
            "No cruces la zona afectada ni regreses por tus pertenencias.",
            "Avisa a tus vecinos y a las autoridades.",
            "No vuelvas hasta que las autoridades lo permitan.",
        ],
    },
    {
        "categoria": "robo",
        "titulo": "Robo",
        "pasos": [
            "Mantén la calma y no opongas resistencia.",
            "Entrega lo que te pidan: tu vida vale más que tus cosas.",
            "Fíjate en detalles como el rostro, la ropa y hacia dónde huye.",
            "Cuando estés a salvo, llama a emergencias y haz el reporte.",
            "Si estás herido, busca atención médica.",
        ],
    },
    {
        "categoria": "medica",
        "titulo": "Emergencias médicas",
        "pasos": [
            "Llama a emergencias y explica qué pasó y dónde estás.",
            "Revisa si la persona responde y respira.",
            "Si hay un sangrado, presiona con un paño limpio.",
            "Sigue las indicaciones de quien te atienda por teléfono.",
            "No muevas a la persona ni le des de comer o beber sin necesidad.",
        ],
    },
    {
        "categoria": "desaparecidos",
        "titulo": "Persona desaparecida",
        "pasos": [
            "No esperes 72 horas: la denuncia se puede hacer de inmediato.",
            "Llama a la Policía (123) o acude a la Fiscalía con una foto reciente y los datos de la persona.",
            "Si crees que es una desaparición forzada, pide ante cualquier juez el Mecanismo de Búsqueda "
            "Urgente (Ley 971 de 2005). Es gratuito y no necesita abogado.",
            "Publica la ficha en RESCATE360 para que la comunidad ayude a buscarla.",
            "Si es menor de edad, avisa también al ICBF (línea 141).",
        ],
    },
    {
        "categoria": "general",
        "titulo": "Líneas de emergencia",
        "pasos": [
            "123: línea nacional de emergencias (Policía, ambulancias, bomberos).",
            "119: Bomberos.",
            "132: Cruz Roja.",
            "144: Defensa Civil.",
            "141: ICBF, para niñas, niños y adolescentes.",
        ],
    },
]
