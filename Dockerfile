# https://developers.home-assistant.io/docs/add-ons/configuration#add-on-dockerfile
ARG BUILD_FROM
FROM $BUILD_FROM

# Install Python dependencies
COPY requirements.txt /tmp/requirements.txt
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt && rm /tmp/requirements.txt

# Copy application code
COPY rootfs /

# Ensure s6 service scripts are executable
RUN chmod +x /etc/services.d/mbus/run /etc/services.d/mbus/finish
