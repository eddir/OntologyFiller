import os
from json import dumps
from django.utils import timezone

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.utils.decorators import method_decorator
from rest_framework.views import APIView
from django_celery_results.models import TaskResult

from kafka import KafkaProducer

from panel.models import Ontology, FilledOntology
from panel.utils import api_response
from panel.tasks.ontologies_tasks import import_ontology_task


class OntologyView(APIView):

    @staticmethod
    def get(request):
        return api_response([{
            "id": onto.id,
            "name": onto.name,
        } for onto in Ontology.objects.all()])

    @staticmethod
    def post(request):
        name = request.data['name']
        parser = request.data['parser']
        url = request.data['url']
        task = import_ontology_task.delay(parser, url, name)
        return api_response(task.id + str(parser) + "lfi0")


class OntologyTasksView(APIView):

    @staticmethod
    def get(request):
        return api_response([{
            "id": task.task_id,
            "name": task.task_name,
            "status": task.status,
            "date_created": task.date_created
        } for task in TaskResult.objects.all()])


class OntologyDownloadView(APIView):
    @method_decorator(login_required)
    @staticmethod
    def get(request, pk):
        filename = "museum-ontology.owl"
        content = Ontology.objects.get(pk=pk).owl
        response = HttpResponse(content, content_type='text/plain')
        response['Content-Disposition'] = 'attachment; filename={0}'.format(filename)
        return response


class OntologyFillView(APIView):

    @method_decorator(login_required)
    @staticmethod
    def get(request):
        return api_response([{
            "id": onto.id,
            "name": onto.name,
            "created_at": onto.created_at,
            "status": onto.status
        } for onto in FilledOntology.objects.all()])

    @method_decorator(login_required)
    @staticmethod
    def post(request):
        """ retrieve owl and facts files from request, save them in the database and run the fill task in kafka """
        owl = request.FILES['owl']
        text = request.FILES['text']

        # save owl and facts files in the database
        ontology = FilledOntology()
        ontology.name = owl.name

        # save with time prefix
        prefix = timezone.now().strftime("%Y%m%d-%H%M%S") + "_"
        ontology.owl.save(prefix + owl.name, owl)
        ontology.text.save(prefix + text.name, text)
        ontology.save()

        print("sending to kafka")
        producer = KafkaProducer(
            bootstrap_servers=os.environ.get('KAFKA_HOST'),
            value_serializer=lambda x: dumps(x).encode('utf-8'),
            api_version=(0, 10, 1)
        )
        print("sending to kafka 2")
        producer.send(os.environ.get('KAFKA_TOPIC'), {
            "id": ontology.id,
            "action": "parse"
        })

        return api_response("Наполнение начато")


class OntologyFillDownloadView(APIView):
    @method_decorator(login_required)
    @staticmethod
    def get(request, pl):
        # assume that the file is already filled and upload to s3
        content = FilledOntology.objects.get(pk=pl)
        filename = ".".join(content.name.split(".")[:-1]) + "_filled.owl"
        raw_data = content.result.read()
        response = HttpResponse(raw_data, content_type='text/plain')
        response['Content-Disposition'] = 'attachment; filename={0}'.format(filename)
        return response
