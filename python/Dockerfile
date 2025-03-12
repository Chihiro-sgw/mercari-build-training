FROM python:3.9.6-alpine

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN apk add --no-cache sqlite

COPY . .

RUN addgroup -S mercari && adduser -S trainee -G mercari
RUN chown -R trainee:mercari /app
RUN chown -R trainee:mercari /app/db
RUN chown -R trainee:mercari /app/images

USER trainee

EXPOSE 9000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "9000"]
