FROM public.ecr.aws/lambda/python:3.9

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app.py ${LAMBDA_TASK_ROOT}
COPY templates/ ${LAMBDA_TASK_ROOT}/templates/

CMD ["app.lambda_handler"]
