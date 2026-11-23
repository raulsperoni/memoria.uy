# Memoria.uy - Visión de Producto

**Lo que pasó en Uruguay, con fuentes. Y lo que pensamos.**

## Qué es

Dos cosas que se alimentan entre sí:

1. **El archivo** ("resistir el archivo"): todas las noticias uruguayas,
   capturadas automáticamente, agrupadas por hecho y convertidas en
   *afirmaciones con procedencia* (cada hecho dice qué medios lo respaldan).
   Guarda cómo cambian las notas después de publicadas. Útil aunque nadie
   entre hoy; imprescindible en momentos políticos.
2. **El juego diario** «¿Qué piensa Uruguay?»: 5 frases opinables de las
   noticias del día. ¿Estás de acuerdo? ¿Y adivinás qué % de Uruguay lo está?
   Resultado compartible. Trae gente todos los días y alimenta las burbujas.

Las **burbujas** agrupan a quienes votan parecido (estilo Polis) y muestran
lo que nos une y lo que nos divide.

Proyecto de interés social, no comercial. Modelo de referencia:
[resistencia.uy](https://resistencia.uy) (LUC Comparada): fuente primaria,
diff, rápido y simple, usado por todos los lados.

## Principios

- **Fuente primaria, no opinión**: los hechos se verifican contra las notas y
  se muestra de dónde sale cada uno.
- **No neutral, pero transparente**: se explica cómo se eligen las frases y
  cómo se arman las burbujas.
- **Sin cuenta**: se juega y vota anónimo; la cuenta es opcional (racha entre
  dispositivos).
- **Agregador, no copia**: lo público son hechos redactados por nosotros,
  resúmenes, citas breves y links. Los snapshots completos son privados y
  sirven de evidencia.
- **Monocromo, mobile-first, rápido.**

## Estado (nov 2026)

- [x] Archivo: ingesta automática, historias, hechos con procedencia,
      verificación, notas editadas, páginas por historia/entidad/medio/día,
      búsqueda, sitemaps
- [x] Juego diario con predicción, puntaje, racha y tarjeta compartible
- [x] Burbujas sobre proposiciones (lo que nos une / nos divide)
- [x] Despliegue con ingesta real (Railway + Cloudflare)
- [x] Imágenes OG generadas, PWA
- [x] Datos abiertos (`/datos/`, CSV)
- [ ] API de solo lectura
- [x] Borrar el sistema viejo (`Noticia`/`Voto`)

## Métricas

- Personas que completan la jornada por día; retorno a 7 días; shares
- Historias y hechos archivados por día; % de hechos verificados
- Notas editadas detectadas
- Costo diario (crawl + LLM)

## Documentación

- [docs/PROPUESTA_2027.md](docs/PROPUESTA_2027.md) — por qué
- [docs/PLAN_2027.md](docs/PLAN_2027.md) — cómo
- [docs/SCIENTIFIC.md](docs/SCIENTIFIC.md) — algoritmos de clustering
- [archivo/README.md](archivo/README.md) — configuración de la ingesta
