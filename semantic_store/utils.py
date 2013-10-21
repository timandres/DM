from django.http import HttpResponse
from rdflib import Graph
from semantic_store.namespaces import NS, bind_namespaces
from datetime import datetime
from contextlib import contextmanager

METADATA_PREDICATES = (
    NS.rdf.type,
    NS.ore.isDescribedBy,
    NS.rdfs.label,
    NS.dc.title,
    NS.dcterms.description,
    NS.exif.width,
    NS.exif.height,
    NS.oa.exact
)

RDFLIB_SERIALIZER_FORMATS = set((
    'n3',
    'nquads',
    'nt',
    'pretty',
    'trig',
    'trix',
    'turtle',
    'xml',
))

def accept_mimetypes(accept_string):
    accept_parts = accept_string.split(',')
    accept_parts = (s.strip() for s in accept_parts)

    for part in accept_parts:
        index_of_semicolon = part.rfind(';')
        format = part[:index_of_semicolon] if index_of_semicolon != -1 else part
        yield format


def negotiated_graph_response(request, graph, close_graph=False, **kwargs):
    bind_namespaces(graph)

    def serialization(format, mimetype):
        body = graph.serialize(format=format)

        if close_graph:
            graph.close()

        return HttpResponse(body, mimetype=mimetype, **kwargs)

    mimetypes = accept_mimetypes(request.META['HTTP_ACCEPT'])

    try:
        mimetype = accept_mimetypes(request.META['HTTP_ACCEPT']).next()
    except StopIteration:
        pass
    else:
        format = mimetype[mimetype.rfind('/') + 1:].strip().lower()
        if format == 'html':
            return serialization('turtle', 'text/turtle')

    for mimetype in mimetypes:
        format = mimetype[mimetype.rfind('/') + 1:].strip().lower()

        if format in RDFLIB_SERIALIZER_FORMATS:
            return serialization(format, mimetype)

    return serialization('turtle', 'text/turtle')

def parse_into_graph(graph=None, **kwargs):
    if graph is None:
        graph = Graph()

    temp_graph = Graph()
    temp_graph.parse(**kwargs)
    for triple in temp_graph:
        graph.add(triple)

    return graph

def parse_request_into_graph(request, graph=None):
    mimetype = request.META['CONTENT_TYPE']

    format = mimetype[mimetype.rfind('/') + 1:].strip()

    index_of_semicolon = format.rfind(';')
    if index_of_semicolon != -1:
        format = format[:index_of_semicolon]

    if format.startswith('rdf+'):
        format = format[4:]

    return parse_into_graph(graph, format=format, data=request.body)

def metadata_triples(graph, subject=None):
    for predicate in METADATA_PREDICATES:
        for t in graph.triples((subject, predicate, None)):
            yield t

@contextmanager
def timed_block(description='untitled operation'):
    start_time = datetime.now()
    yield
    end_time = datetime.now()
    print '- %s excecuted in %s' % (description, end_time-start_time)

