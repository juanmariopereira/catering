"""
Crea los tipos de ingrediente (Lácteos, Hortalizas, Carnes, etc.) y asigna
el tipo correspondiente a cada ingrediente según su nombre.
"""
import re
from django.core.management.base import BaseCommand
from recipes.models import TipoIngrediente, Ingrediente


# Lista de tipos con orden de visualización
TIPOS_NOMBRES_ORDEN = [
    ('Hortalizas', 1),
    ('Frutas', 2),
    ('Setas', 3),
    ('Carnes', 4),
    ('Aves', 5),
    ('Pescados y mariscos', 6),
    ('Lácteos', 7),
    ('Huevos', 8),
    ('Cereales', 9),
    ('Legumbres', 10),
    ('Aceites', 11),
    ('Vinagres', 12),
    ('Salsas y condimentos', 13),
    ('Sazonadores y especias', 14),
    ('Frutos secos', 15),
    ('Dulces y endulzantes', 16),
    ('Bebidas', 17),
    ('Caldos y bases', 18),
    ('Otros', 19),
]


def _normalize(s):
    return (s or '').strip().lower()


def get_tipo_por_nombre(nombre):
    """
    Determina el tipo de ingrediente por palabras clave en el nombre.
    El orden de las comprobaciones importa (más específico primero).
    """
    n = _normalize(nombre)
    if not n:
        return 'Otros'

    # Setas (antes de "champiñón" como verdura)
    if any(x in n for x in ['champiñón', 'shiitake', 'seta', 'portobello', 'ostra seta']):
        return 'Setas'

    # Bebidas (leche de X, bebida de X, zumo, etc.)
    if any(x in n for x in ['leche de almendras', 'leche de avena', 'leche de coco', 'bebida de ', 'zumo de ', 'zumo ', 'refresco', 'vino ', 'vinos ', 'cerveza', 'sidra', 'cava', 'café', 'té ', 'tés ', 'infusión', 'tonica', 'tónica', 'horchata', 'granizado', 'bebida isotónica', 'agua con gas']):
        return 'Bebidas'

    # Caldos y bases
    if any(x in n for x in ['caldo de ', 'caldo ', 'caldos concentrados']):
        return 'Caldos y bases'
    if n == 'agua':
        return 'Caldos y bases'

    # Lácteos
    if any(x in n for x in ['leche ', 'leche entera', 'leche semidesnatada', 'leche desnatada', 'leche sin lactosa', 'leche condensada', 'leche evaporada', 'leche en polvo', 'nata ', 'crema de leche', 'yogur ', 'kéfir', 'kefir', 'cuajada', 'requesón', 'quark', 'mantequilla', 'queso ', 'burrata', 'bocconcini', 'mascarpone', 'philadelphia', 'nata agria', 'crème fraîche', 'creme fraiche', 'suero de mantequilla', 'yogur de soja']):
        return 'Lácteos'

    # Salsas y condimentos
    if any(x in n for x in ['ketchup', 'mayonesa', 'salsa de soja', 'worcester', 'tabasco']):
        return 'Salsas y condimentos'

    # Aceites
    if 'aceite' in n:
        return 'Aceites'

    # Vinagres
    if 'vinagre' in n:
        return 'Vinagres'

    # Huevos
    if any(x in n for x in ['huevo', 'clara de huevo', 'yema de huevo', 'huevo codorniz']):
        return 'Huevos'

    # Cereales y harinas (incl. quinoa, bulgur, couscous)
    if any(x in n for x in ['harina ', 'harina de', 'arroz ', 'arroz blanco', 'arroz integral', 'arroz basmati', 'arroz jazmín', 'arroz bomba', 'arroz salvaje', 'pasta ', 'espagueti', 'macarrones', 'tallarines', 'fideos', 'lasagna', 'canelones', 'tortilla de trigo', 'tortilla de maíz', 'polenta', 'trigo', 'cebada', 'mijo', 'amaranto', 'trigo sarraceno', 'copos de avena', 'copos de maíz', 'muesli', 'granola', 'maicena', 'fécula de patata', 'pan rallado', 'levadura nutricional', 'almidón de maíz', 'quinoa', 'bulgur', 'couscous', 'cuscús']):
        return 'Cereales'

    # Legumbres (granos secos)
    if any(x in n for x in ['lenteja', 'garbanzo', 'alubia', 'guisante seco', 'haba seca', 'soja', 'edamame', 'azuki', 'judía mungo', 'judías mungo']):
        return 'Legumbres'

    # Sazonadores y especias (antes que Carnes/Pescados para no confundir romero con mero)
    if any(x in n for x in ['sal', 'pimienta', 'pimentón', 'canela', 'nuez moscada', 'clavo', 'jengibre', 'cúrcuma', 'comino', 'cilantro', 'orégano', 'albahaca', 'tomillo', 'romero', 'laurel', 'perejil', 'eneldo', 'estragón', 'mejorana', 'mostaza', 'levadura química', 'bicarbonato', 'gelatina', 'agar-agar', 'pectina', 'levadura fresca', 'levadura seca']):
        return 'Sazonadores y especias'

    # Aves (después de sazonadores; "oca" sin espacio para no confundir)
    if any(x in n for x in ['pollo', 'pavo', 'codorniz', 'pato', 'oca']):
        return 'Aves'

    # Carnes (y embutidos); excluir "filete de lenguado" etc.
    if any(x in n for x in ['ternera', 'cordero', 'cerdo', 'bacon', 'jamón', 'jamon', 'chorizo', 'salchicha', 'morcilla', 'butifarra', 'solomillo', 'filete', 'carne picada', 'lomo de cerdo', 'costilla de cerdo', 'costilla de ternera', 'costilla de cordero', 'pierna de cordero', 'falda', 'aguja', 'redondo', 'cadera', 'entrecot', 'chuletón', 'cecina', 'lacón', 'panceta', 'mortadela', 'salami', 'fiambre', 'rabo de toro', 'secreto ibérico', 'presa ibérica', 'solomillo ibérico', 'carne de vaca', 'longaniza', 'longaniz', 'fuet', 'morcón', 'lomo embuchado']):
        if not any(p in n for p in ['lenguado', 'merluza', 'salmón', 'salmon', 'atún', 'atun', 'bacalao', 'pescado', 'rape', 'trucha']):
            return 'Carnes'

    # Pescados y mariscos (antes que Aceites para "anchoa en aceite")
    if any(x in n for x in ['salmón', 'salmon', 'atún', 'atun', 'bacalao', 'merluza', 'lubina', 'dorada', 'trucha', 'lenguado', 'rape', 'pescadilla', 'caballa', 'sardina', 'anchoa', 'boquerón', 'bonito', 'pulpo', 'calamar', 'sepia', 'gamba', 'langostino', 'mejillón', 'mejillones', 'almeja', 'berberecho', 'vieira', 'cangrejo', 'langosta', 'bogavante', 'pescado ', 'tilapia', 'perca', 'rodaballo', 'mero', 'corvina', 'cazón', 'raya', 'surimi', 'palito', 'caviar', 'hueva']):
        return 'Pescados y mariscos'

    # Frutos secos
    if any(x in n for x in ['almendra', 'nuez', 'avellana', 'cacahuete', 'pistacho', 'macadamia', 'brasil', 'pipas de', 'piñón', 'pinon', 'castaña', 'castana', 'coco rallado', 'pecana', 'marañón', 'maranon']):
        return 'Frutos secos'

    # Dulces y endulzantes
    if any(x in n for x in ['miel', 'mermelada', 'confitura', 'crema de cacao', 'chocolate', 'cacao en polvo', 'azúcar', 'azucar', 'edulcorante', 'sirope', 'dulce de leche', 'caramelo', 'nata montada para repostería', 'masa de hojaldre', 'masa de brisa', 'masa quebrada']):
        return 'Dulces y endulzantes'

    # Hortalizas (antes que Carnes/Frutas para repollo, col, calabacín redondo, calabaza cacahuete, boniato morado)
    if any(x in n for x in ['tomate', 'lechuga', 'cebolla', 'zanahoria', 'pimiento', 'brócoli', 'brocoli', 'coliflor', 'espinaca', 'acelga', 'col', 'repollo', 'berenjena', 'calabacín', 'calabacin', 'pepino', 'apio', 'judía verde', 'judias verde', 'judías verdes', 'guisante', 'haba', 'espárrago', 'esparrago', 'puerro', 'remolacha', 'nabo', 'rábano', 'rabano', 'ajo', 'alcachofa', 'calabaza', 'endibia', 'escarola', 'rúcula', 'rucula', 'canónigo', 'canonigo', 'hinojo', 'col kale', 'pak choi', 'maíz dulce', 'maiz dulce', 'alubia verde', 'tomate cherry', 'cebolleta', 'pepinillo', 'oliva', 'alcaparra', 'alga', 'col lombarda', 'brécol', 'brecol', 'romanesco', 'coles de bruselas', 'acelga roja', 'espinaca baby', 'rúcula baby', 'mix de ensalada', 'zanahoria baby', 'tomate raf', 'tomate kumato', 'pimiento italiano', 'cebolla morada', 'cebolla dulce', 'chalota', 'berenjena japonesa', 'calabacín redondo', 'calabaza butternut', 'calabaza cacahuete', 'boniato', 'boniato morado', 'ñame', 'yuca', 'plátano macho', 'okra']):
        return 'Hortalizas'

    # Frutas (incl. frutas secas, aguacate, tomate pera; no boniato)
    if any(x in n for x in ['manzana', 'pera', 'plátano', 'platano', 'naranja', 'mandarina', 'limón', 'limon', 'lima', 'uva', 'fresa', 'cereza', 'melocotón', 'albaricoque', 'ciruela', 'sandía', 'sandia', 'melón', 'melon', 'kiwi', 'piña', 'pina', 'mango', 'papaya', 'granada', 'higo', 'dátil', 'datil', 'arándano', 'arandano', 'frambuesa', 'mora', 'grosella', 'clementina', 'pomelo', 'maracuyá', 'guayaba', 'litchi', 'coco fresco', 'coco', 'aguacate', 'caqui', 'níspero', 'nispero', 'chirimoya', 'physalis', 'pitaya', 'carambola', 'uva pasa', 'ciruela pasa', 'higo seco', 'dátil seco', 'orejones', 'cranberry', 'endrina', 'zarzamora', 'mirtilo', 'tomate pera']):
        return 'Frutas'

    # Proteínas vegetales / otros
    if any(x in n for x in ['tofu', 'tempeh', 'seitán', 'seitan']):
        return 'Otros'

    return 'Otros'


# Lista id,nombre proporcionada por el usuario (372-871)
INGREDIENTES_LISTA = """372,Tomate
373,Lechuga
374,Cebolla
375,Zanahoria
376,Pimiento rojo
377,Pimiento verde
378,Pimiento amarillo
379,Brócoli
380,Coliflor
381,Espinaca
382,Acelga
383,Col
384,Repollo
385,Berenjena
386,Calabacín
387,Pepino
388,Apio
389,Judías verdes
390,Guisantes
391,Habas
392,Espárragos
393,Puerro
394,Remolacha
395,Nabo
396,Rábano
397,Ajo
398,Alcachofa
399,Boniato
400,Calabaza
401,Puerro grueso
402,Endibia
403,Escarola
404,Rúcula
405,Canónigos
406,Hinojo
407,Col kale
408,Pak choi
409,Maíz dulce
410,Champiñón
411,Shiitake
412,Ostra seta
413,Portobello
414,Pimiento de Padrón
415,Alubia verde
416,Calabacín italiano
417,Tomate cherry
418,Tomate pera
419,Cebolleta
420,Pepinillo
421,Aguacate Hass
422,Oliva
423,Alcaparra
424,Alga nori
425,Alga wakame
426,Manzana
427,Pera
428,Plátano
429,Naranja
430,Mandarina
431,Limón
432,Lima
433,Uva
434,Fresa
435,Cereza
436,Melocotón
437,Albaricoque
438,Ciruela
439,Sandía
440,Melón
441,Kiwi
442,Piña
443,Mango
444,Papaya
445,Granada
446,Higo
447,Dátil
448,Arándano
449,Frambuesa
450,Mora
451,Grosella
452,Clementina
453,Pomelo
454,Maracuyá
455,Guayaba
456,Litchi
457,Coco
458,Aguacate fuerte
459,Caqui
460,Níspero
461,Chirimoya
462,Uva pasa
463,Ciruela pasa
464,Higo seco
465,Dátil seco
466,Orejones
467,Cranberry
468,Arándano rojo
469,Endrina
470,Zarzamora
471,Fresa silvestre
472,Mirtilo
473,Physalis
474,Pitaya
475,Carambola
476,Granada blanca
477,Uva moscatel
478,Melón galia
479,Melón cantalupo
480,Pollo
481,Pechuga de pollo
482,Muslo de pollo
483,Pavo
484,Pechuga de pavo
485,Codorniz
486,Pato
487,Oca
488,Pollo campero
489,Pollo entero
490,Ternera
491,Solomillo de ternera
492,Filete de ternera
493,Carne picada de ternera
494,Cordero
495,Pierna de cordero
496,Costilla de cordero
497,Cerdo
498,Lomo de cerdo
499,Solomillo de cerdo
500,Bacon
501,Jamón serrano
502,Jamón cocido
503,Chorizo
504,Salchicha
505,Morcilla
506,Butifarra
507,Lacón
508,Panceta
509,Costilla de cerdo
510,Salmón
511,Atún
512,Bacalao
513,Merluza
514,Lubina
515,Dorada
516,Trucha
517,Lenguado
518,Rape
519,Pescadilla
520,Caballa
521,Sardina
522,Anchoa
523,Boquerón
524,Bonito
525,Pulpo
526,Calamar
527,Sepia
528,Gamba
529,Langostino
530,Mejillón
531,Almeja
532,Berberecho
533,Vieira
534,Cangrejo
535,Langosta
536,Bogavante
537,Pescado blanco
538,Tilapia
539,Perca
540,Rodaballo
541,Mero
542,Corvina
543,Cazón
544,Raya
545,Leche entera
546,Leche semidesnatada
547,Leche desnatada
548,Leche sin lactosa
549,Nata líquida
550,Nata para cocinar
551,Crema de leche
552,Yogur natural
553,Yogur griego
554,Yogur desnatado
555,Kéfir
556,Cuajada
557,Requesón
558,Quark
559,Mantequilla
560,Queso fresco
561,Queso tierno
562,Queso curado
563,Queso manchego
564,Queso parmesano
565,Queso mozzarella
566,Queso cheddar
567,Queso emmental
568,Queso brie
569,Queso camembert
570,Queso azul
571,Queso feta
572,Queso ricotta
573,Queso cottage
574,Queso crema
575,Leche condensada
576,Leche evaporada entera
577,Nata montada batida
578,Yogur de soja
579,Leche de almendras
580,Leche de avena
581,Harina de trigo
582,Harina integral
583,Harina de fuerza
584,Harina de maíz
585,Harina de centeno
586,Harina de avena
587,Harina de garbanzo
588,Harina de almendra
589,Maicena
590,Fécula de patata
591,Pan rallado
592,Copos de avena
593,Copos de maíz
594,Muesli
595,Granola
596,Arroz blanco
597,Arroz integral
598,Arroz basmati
599,Arroz jazmín
600,Arroz bomba
601,Arroz salvaje
602,Quinoa
603,Bulgur
604,Couscous
605,Cuscús integral
606,Pasta de huevo
607,Pasta integral
608,Espagueti
609,Macarrones
610,Tallarines
611,Fideos
612,Lasagna
613,Canelones
614,Tortilla de trigo
615,Tortilla de maíz
616,Polenta
617,Trigo
618,Cebada
619,Mijo
620,Amaranto
621,Trigo sarraceno
622,Lentejas
623,Garbanzos
624,Alubias blancas
625,Alubias rojas
626,Alubias pintas
627,Guisantes secos
628,Habas secas
629,Soja
630,Edamame
631,Azuki
632,Judías mungo
633,Lenteja roja
634,Lenteja beluga
635,Garbanzo negro
636,Alubia negra
637,Aceite de oliva
638,Aceite de girasol
639,Aceite de maíz
640,Aceite de soja
641,Aceite de coco
642,Aceite de sésamo
643,Aceite de lino
644,Vinagre de vino
645,Vinagre de manzana
646,Vinagre balsámico
647,Vinagre de Jerez
648,Sal
649,Pimienta negra
650,Pimienta blanca
651,Pimentón dulce
652,Pimentón picante
653,Canela
654,Nuez moscada
655,Clavo
656,Jengibre
657,Cúrcuma
658,Comino
659,Cilantro
660,Orégano
661,Albahaca
662,Tomillo
663,Romero
664,Laurel
665,Perejil
666,Eneldo
667,Estragón
668,Mejorana
669,Mostaza
670,Ketchup
671,Mayonesa
672,Salsa de soja
673,Worcester
674,Tabasco
675,Caldos concentrados
676,Levadura química
677,Bicarbonato
678,Gelatina
679,Almendra
680,Nuez
681,Avellana
682,Cacahuete
683,Pistacho
684,Nuez de macadamia
685,Nuez de Brasil
686,Pipas de girasol
687,Pipas de calabaza
688,Piñón
689,Castaña
690,Coco rallado
691,Nuez pecana
692,Marañón
693,Almendra laminada
694,Nuez troceada
695,Huevo
696,Clara de huevo
697,Yema de huevo
698,Huevo codorniz
699,Tofu
700,Tempeh
701,Seitan
702,Levadura fresca
703,Levadura seca
704,Miel
705,Mermelada
706,Confitura
707,Crema de cacao
708,Chocolate negro
709,Chocolate con leche
710,Chocolate blanco
711,Cacao en polvo
712,Azúcar blanco
713,Azúcar moreno
714,Edulcorante
715,Sirope de arce
716,Sirope de agave
717,Dulce de leche
718,Caramelo
719,Nata montada para repostería
720,Masa de hojaldre
721,Masa de brisa
722,Masa quebrada
723,Levadura nutricional
724,Agar-agar
725,Pectina
726,Almidón de maíz
727,Agua
728,Caldo de pollo
729,Caldo de carne
730,Caldo de verduras
731,Caldo de pescado
732,Vino blanco
733,Vino tinto
734,Vino rosado
735,Cerveza
736,Sidra
737,Cava
738,Café
739,Café descafeinado
740,Té negro
741,Té verde
742,Té rojo
743,Infusión
744,Zumo de naranja
745,Zumo de limón
746,Zumo de manzana
747,Zumo de tomate
748,Refresco cola
749,Refresco naranja
750,Tónica
751,Agua con gas
752,Bebida isotónica
753,Leche de coco
754,Bebida de arroz
755,Bebida de avena
756,Horchata
757,Granizado
758,Col lombarda
759,Brécol
760,Romanesco
761,Coles de Bruselas
762,Acelga roja
763,Espinaca baby
764,Rúcula baby
765,Mix de ensalada
766,Zanahoria baby
767,Tomate raf
768,Tomate kumato
769,Pimiento italiano
770,Cebolla morada
771,Cebolla dulce
772,Chalota
773,Puerro fino
774,Berenjena japonesa
775,Calabacín redondo
776,Calabaza butternut
777,Calabaza cacahuete
778,Boniato morado
779,Ñame
780,Yuca
781,Plátano macho
782,Okra
783,Manzana golden
784,Manzana fuji
785,Manzana granny
786,Pera conferencia
787,Pera blanquilla
788,Naranja sanguina
789,Naranja navel
790,Mandarina satsuma
791,Uva blanca
792,Uva negra
793,Uva moscatel negra
794,Melón piel de sapo
795,Sandía sin pepitas
796,Piña gold
797,Mango kent
798,Mango ataulfo
799,Papaya maradol
800,Granada mollar
801,Coco fresco
802,Dátil medjool
803,Higo breva
804,Chirimoya cumbe
805,Caqui persimon
806,Níspero japonés
807,Pollo ecológico
808,Pavo ahumado
809,Jamón ibérico
810,Jamón York
811,Fiambre de pavo
812,Fiambre de pollo
813,Mortadela
814,Salami
815,Cecina
816,Lomo embuchado
817,Fuet
818,Longaniza
819,Morcón
820,Carne de vaca vieja
821,Entrecot
822,Chuletón
823,Falda
824,Aguja
825,Redondo
826,Cadera
827,Solomillo ibérico
828,Secreto ibérico
829,Presa ibérica
830,Costilla de ternera
831,Rabo de toro
832,Salmón ahumado
833,Atún en conserva
834,Bonito del norte
835,Anchoa en aceite
836,Sardina en conserva
837,Caballa en conserva
838,Mejillones en conserva
839,Almejas en conserva
840,Surimi
841,Palitos de cangrejo
842,Caviar
843,Hueva
844,Bacalao salado
845,Bacalao desalado
846,Merluza congelada
847,Filete de lenguado
848,Trucha ahumada
849,Salmón marinado
850,Leche evaporada desnatada
851,Leche en polvo
852,Suero de mantequilla
853,Queso gruyer
854,Queso gouda
855,Queso edam
856,Queso provolone
857,Queso roquefort
858,Queso cabrales
859,Queso idiazábal
860,Queso tetilla
861,Queso mahón
862,Queso payoyo
863,Queso de cabra
864,Queso de oveja
865,Burrata
866,Bocconcini
867,Queso mascarpone
868,Queso philadelphia
869,Nata agria
870,Crème fraîche
871,Yogur bebible
"""


class Command(BaseCommand):
    help = 'Crea tipos de ingrediente (Lácteos, Hortalizas, etc.) y asigna el tipo a cada ingrediente por ID/nombre.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Solo mostrar qué se haría, sin guardar.',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        if dry_run:
            self.stdout.write(self.style.WARNING('Modo dry-run: no se guardará nada.'))

        # 1. Crear tipos
        tipos_by_nombre = {}
        for nombre, orden in TIPOS_NOMBRES_ORDEN:
            if dry_run:
                tipos_by_nombre[nombre] = None
                self.stdout.write(f'  Crearía tipo: {nombre} (orden {orden})')
            else:
                t, created = TipoIngrediente.objects.get_or_create(
                    nombre=nombre,
                    defaults={'orden': orden, 'activo': True}
                )
                tipos_by_nombre[nombre] = t
                if created:
                    self.stdout.write(self.style.SUCCESS(f'  Creado tipo: {nombre}'))

        if dry_run:
            self.stdout.write('')
            # En dry-run no tenemos objetos TipoIngrediente; usamos nombre para asignación simbólica
            pass

        # 2. Parsear lista de ingredientes
        lineas = [ln.strip() for ln in INGREDIENTES_LISTA.strip().splitlines() if ln.strip()]
        asignados = 0
        no_encontrados = []
        sin_tipo = []

        for ln in lineas:
            if ',' not in ln:
                continue
            parte = ln.split(',', 1)
            try:
                id_ing = int(parte[0].strip())
            except ValueError:
                continue
            nombre_ing = (parte[1] if len(parte) > 1 else '').strip()
            if not nombre_ing:
                continue

            tipo_nombre = get_tipo_por_nombre(nombre_ing)
            if dry_run:
                self.stdout.write(f'  {id_ing} {nombre_ing!r} -> {tipo_nombre}')
                asignados += 1
                continue

            tipo = tipos_by_nombre.get(tipo_nombre)
            if not tipo:
                sin_tipo.append((id_ing, nombre_ing, tipo_nombre))
                continue

            try:
                ing = Ingrediente.objects.get(pk=id_ing)
            except Ingrediente.DoesNotExist:
                no_encontrados.append((id_ing, nombre_ing))
                continue

            ing.tipo_ingrediente = tipo
            ing.save()
            asignados += 1

        self.stdout.write(self.style.SUCCESS(f'Asignados: {asignados} ingredientes.'))
        if no_encontrados:
            self.stdout.write(self.style.WARNING(f'No encontrados por ID: {len(no_encontrados)}'))
            for id_ing, nombre_ing in no_encontrados[:20]:
                self.stdout.write(f'  ID {id_ing}: {nombre_ing}')
            if len(no_encontrados) > 20:
                self.stdout.write(f'  ... y {len(no_encontrados) - 20} más.')
        if sin_tipo and not dry_run:
            self.stdout.write(self.style.WARNING(f'Sin tipo asignado: {len(sin_tipo)}'))
            for id_ing, nombre_ing, tipo_nombre in sin_tipo[:10]:
                self.stdout.write(f'  ID {id_ing}: {nombre_ing} -> tipo {tipo_nombre!r}')
