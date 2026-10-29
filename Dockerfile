FROM python:3.11.14-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .

RUN python -m pip install pip==26.2.2 \
    && python -m pip install -r requirements.txt

COPY ingestion ./ingestion
COPY orchestration ./orchestration
COPY transformations ./transformations
COPY docs ./docs
COPY dashboard ./dashboard
COPY .streamlit ./.streamlit
COPY tests ./tests
EXPOSE 8501
CMD ["python", "orchestration/pipeline.py"]
