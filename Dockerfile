FROM python:3

WORKDIR /usr/src/app

COPY setup.py .

RUN pip install --no-cache-dir .

COPY . .

CMD ["python", "./driver.py"]
