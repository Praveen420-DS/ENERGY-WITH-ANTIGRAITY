FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci --include=optional
COPY . .
RUN npm run build

FROM alpine:3.20
WORKDIR /app
COPY --from=build /app/dist /app/dist
RUN addgroup -S app && adduser -S -G app app \
    && mkdir -p /output && chown app:app /output
CMD ["sh", "-c", "chown -R app:app /output && su app -s /bin/sh -c 'cp -R /app/dist/. /output/'"]
