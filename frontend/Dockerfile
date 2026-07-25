FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM alpine:3.20
WORKDIR /app
COPY --from=build /app/dist /app/dist
CMD ["sh", "-c", "mkdir -p /output && cp -R /app/dist/. /output/"]
