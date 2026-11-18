# Imagen para Cloud Run. Antes de deployar: python construir.py
FROM nginx:1.27-alpine
RUN rm -f /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/conf.d/indartubo.conf
COPY sitio/ /usr/share/nginx/html/
EXPOSE 8080
