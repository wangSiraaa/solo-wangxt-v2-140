# 多阶段：前端构建 + 后端运行（前端产物由 FastAPI 静态托管，单容器即完整应用）
FROM node:20-alpine AS frontend
WORKDIR /fe
COPY frontend/package.json ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim
WORKDIR /app
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
COPY backend/tests ./tests
COPY --from=frontend /fe/dist ./frontend/dist
ENV DATABASE_URL=postgresql+psycopg2://xrd:xrd@db:5432/xrd
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
