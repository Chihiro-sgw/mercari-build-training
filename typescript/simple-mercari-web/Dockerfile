FROM node:20-alpine
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm install 
COPY . .

RUN addgroup -S mercari && adduser -S trainee -G mercari
RUN chown -R trainee:mercari /app
USER trainee

 EXPOSE 3000

CMD ["npm", "start", "--", "--host", "0.0.0.0"]
