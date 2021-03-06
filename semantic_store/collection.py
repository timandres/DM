import os
from urllib2 import urlopen
from argparse import ArgumentParser
import pickle
from rdflib.graph import ConjunctiveGraph
from rdflib.term import URIRef
from rdflib import RDF
from semantic_store.namespaces import ns, bind_namespaces, update_old_namespaces, NS
from semantic_store.utils import parse_into_graph

"""
Example:

python collection.py --pages BeineckeMS525 --col_uri http://manifests.ydc2.yale.eduMetaManifest.xml --col_url http://openmanifests.s3-website-us-east-1.amazonaws.com/MetaManifest.xml
"""


def resource_url(resource_uri, g):
    return g.value(None, NS.ore.describes, URIRef(resource_uri))


def resource_uri(resource_url, g):
    return g.value(URIRef(resource_url), NS.ore.describes, None)
    

def find_resource(manifest_uri, g, pred, obj):
    bind_namespaces(g)
    query = """SELECT DISTINCT ?resource_uri ?resource_url
               WHERE {
                   <%s> ore:aggregates ?resource_uri .
                   ?resource_url ore:describes ?resource_uri .
                   ?resource_uri %s "%s" .
               }""" % (manifest_uri, pred, obj)
    qres = g.query(query, initNs = ns)
    return qres
    

def list_resources(manifest_uri, g):
    uri_by_title = {}
    for uri in g.objects(URIRef(manifest_uri), ns['ore']['aggregates']):
        for title in g.objects(uri, ns['dc']['title']):
            uri_by_title[title] = uri
    for t in sorted(uri_by_title.keys()):
        print "%s, %s" % (t, uri_by_title[t])


def resource_urls(manifest_uri, g):
    bind_namespaces(g)
    query = """SELECT DISTINCT ?resource_url
               WHERE {
                   ?manifest_uri ore:aggregates ?resource_uri .
                   ?resource_url ore:describes ?resource_uri
               }"""
    qres = g.query(query, initNs=ns, initBindings={'manifest_uri': URIRef(manifest_uri)})
    if len(qres) == 0:
        query = """SELECT DISTINCT ?resource_url
                   WHERE {
                       ?manifest_uri ore:aggregates ?resource_uri .
                       ?resource_uri ore:isDescribedBy ?resource_url
                   }"""
        qres = g.query(query, initNs=ns, initBindings={'manifest_uri': URIRef(manifest_uri)})
    return qres


def aggregated_uris_urls(uri, g):
    bind_namespaces(g)
    query = """SELECT DISTINCT ?resource_uri ?resource_url
               WHERE {
                   ?uri ore:aggregates ?resource_uri .
                   OPTIONAL { ?resource_url ore:describes ?resource_uri } .
                   OPTIONAL { ?resource_uri ore:isDescribedBy ?resource_url }
               }"""
    qres = g.query(query, initNs=ns, initBindings={'uri': URIRef(uri)})
    return list(qres)


def resource_uris_urls_old(manifest_uri, g):
    bind_namespaces(g)
    query = """SELECT DISTINCT ?resource_uri ?resource_url
               WHERE {
                   ?manifest_uri ore:aggregates ?resource_uri .
                   ?resource_url ore:describes ?resource_uri
               }"""
    qres = g.query(query, initNs=ns, initBindings={'manifest_uri': URIRef(manifest_uri)})
    uris_urls = set(qres)

    query = """SELECT DISTINCT ?resource_uri ?resource_url
               WHERE {
                   ?manifest_uri ore:aggregates ?resource_uri .
                   ?resource_uri ore:isDescribedBy ?resource_url
               }"""
    qres = g.query(query, initNs=ns, initBindings={'manifest_uri': URIRef(manifest_uri)})
    for i in qres:
        uris_urls.add(i)

    return uris_urls


def image_annotations(manifest_uri, g):
    bind_namespaces(g)
    query = """SELECT DISTINCT ?resource_uri ?resource_url
               WHERE {
                   ?manifest_uri ore:aggregates ?resource_uri .
                   ?resource_uri rdf:type dms:ImageAnnotationList .
                   OPTIONAL { ?resource_url ore:describes ?resource_uri } .
                   OPTIONAL { ?resource_uri ore:isDescribedBy ?resource_url }
               }"""
    qres = g.query(query, initNs=ns, initBindings={'manifest_uri': URIRef(manifest_uri)})
    return list(qres)


def aggregated_seq_uris_urls(uri, g):
    bind_namespaces(g)
    query = """SELECT DISTINCT ?resource_uri ?resource_url
               WHERE {
                   ?uri ore:aggregates ?resource_uri .
                   {?resource_uri a dms:Sequence} UNION {?resource_uri a sc:Sequence} .
                   OPTIONAL { ?resource_url ore:describes ?resource_uri } .
                   OPTIONAL { ?resource_uri ore:isDescribedBy ?resource_url }
               }"""
    qres = g.query(query, initNs=ns, initBindings={'uri': uri})
    return list(qres)

def fetch_and_parse(url, g, manifest_file=None, fmt="xml", cache=None):
    if (not cache) or (cache and (url not in cache['urls'])):
        if manifest_file:
            parse_into_graph(g, source=manifest_file, format=fmt)
        else:
            print "fetching:", url
            response = urlopen(url)
            rdf_str = response.read()
            rdf_str = rdf_str.replace("rdf:nodeID=\"urn:uuid:", "rdf:nodeID=\"_") 
            parse_into_graph(g, data=rdf_str, format=fmt)
    if cache:
        cache['urls'].add(url)

    update_old_namespaces(g)


def harvest_resource_triples(g, collection_uri=None, pred=None, obj=None, 
                             res_uri=None, res_url=None, cache=None, fmt="xml"):
    if collection_uri and pred and obj:
        qres = find_resource(collection_uri, g, pred, obj)
        (res_uri, res_url) = list(qres)[0]
        fetch_and_parse(res_url, g, fmt, cache)
    qres = resource_urls(res_uri, g)
    for (component_url,) in qres:
        fetch_and_parse(component_url, g, fmt=fmt, cache=cache)
    return res_uri, res_url


def page_attributes(g, page_uri, res_uri):
    bind_namespaces(g)
    qres = g.query("""SELECT DISTINCT ?res_title ?title ?width ?height ?image 
               WHERE {
                   {?res_uri dc:title ?res_title} UNION {?res_uri rdfs:label ?res_title} .
                   {?page_uri dc:title ?title} UNION {?page_uri rdfs:label ?title} .
                   ?page_uri exif:width ?width .
                   ?page_uri exif:height ?height .
                   ?anno oa:hasTarget ?page_uri .
                   ?anno oa:hasBody ?image .
                   ?image rdf:type dcmitype:Image .
               }""", initBindings={
        'res_uri': URIRef(res_uri),
        'page_uri': URIRef(page_uri)
    })
    if qres:
        (res_title, page_title, width, height, image) = list(qres)[0]
        return (unicode(res_title), unicode(page_title), int(width), int(height), 
                unicode(image))
    else:
        return None, None, None, None, None



def pagination(g, collection_uri=None, pred=None, obj=None, 
               res_uri=None, cache=None, fmt="xml"):

    def one_page(g, page_uri, res_uri, seq_uri, seq_num):
        (res_title, page_title, width, height, image) = page_attributes(g, 
                                                                        page_uri, 
                                                                        res_uri)
        # print "%s | %s | %s | %s | %s | %s | %s | %s | %s" % (
        #     seq_num, page_title, page_uri, width, height, image, seq_uri, res_uri, 
        #     res_title)
        if not width:
            print "no width for page:", page_uri
        page = {'manuscript_title': unicode(res_title), 
                'manuscript_uri': unicode(res_uri),
                'canvas_title': unicode(page_title), 
                'canvas_uri': unicode(page_uri), 
                'canvas_image_uri': unicode(image), 
                'canvas_width': int(width), 
                'canvas_height': int(height), 
                'canvas_sequence_uri': unicode(seq_uri),
                'canvas_sequence_num': int(seq_num)}
        return page

        
    (res_uri, res_url) = harvest_resource_triples(g, 
                                                  collection_uri=collection_uri, 
                                                  res_uri=res_uri, 
                                                  pred=pred, 
                                                  obj=obj,
                                                  cache=cache, 
                                                  fmt=fmt)

    query = """SELECT DISTINCT ?first ?rest ?sequence_uri
               WHERE {
                   ?res_uri ore:aggregates ?sequence_uri .
                   ?sequence_uri rdf:first ?first .
                   {?first a dms:Canvas} UNION {?first a sc:Canavas} .
                   ?sequence_uri rdf:rest ?rest
               }"""
    qres = g.query(query, initNs=ns, initBindings={'res_uri': res_uri})

    (first, rest, seq_uri) = list(qres)[0]
    seq_num = 1
    page = one_page(g, first, res_uri, seq_uri, seq_num)
    pages = [page]
    while rest != RDF.nil:
        first = list(g.objects(rest, RDF.first))[0]
        rest = list(g.objects(rest, RDF.rest))[0]
        seq_num += 1
        page = one_page(g, first, res_uri, seq_uri, seq_num)
        pages.append(page)
    return pages


# def create_graph(args):
#     if args.store:
#         config_filename = args.store
#         kwargs = dict()
#         for i in open(config_filename):
#             k, v = i.split("=")
#             kwargs[k.strip()] = v.strip()
#         g = db.storebacked_graph(**kwargs)
#         return g
#     elif args.pickle:
#         g = load_cache(args.cache)
#         return g
#     else:
#         pass

def load_cache(cache_filename):
    cache = {'urls': set(),
             'g': ConjunctiveGraph()}
    if not cache_filename:
        return cache
    if not os.path.exists(cache_filename):
        return cache
    f = open(cache_filename, "rb")
    cache = pickle.load(f)
    g_serialized = cache['g']
    g = ConjunctiveGraph()
    g.parse(data=g_serialized)
    cache['g'] = g
    f.close()
    return cache


def save_cache(cache_filename, cache):
    if not cache_filename:
        return 
    f = open(cache_filename, "wb")
    cache['g'] = cache['g'].serialize()
    pickle.dump(cache, f)
    f.close()
        
    
def __col_manifest_url(args):
    if args.col_url:
        url = args.col_url
    else:
        url = "%s.%s" % (args.col_uri, args.fmt)
    return url


if __name__ == "__main__":
    parser = ArgumentParser(
        description="Utilities for working with resources in a collection.")
    parser.add_argument("--list", 
                        dest="uri",
                        help="List resources for the collection.")
    parser.add_argument("--find", 
                        default=None,
                        help="Find a specific resource.")
    parser.add_argument("--pages", 
                        default=None,
                        help="List pages for specific resource.")
    parser.add_argument("--col_uri", 
                        help="URI of the collection manifest.")
    parser.add_argument("--col_url", 
                        default=None,
                        help="URL of the collection manifest" +
                        " (In case url can't be easily determined from URI).")
    parser.add_argument("--res_url", 
                        default=None,
                        help="URL of the resource manifest")
    parser.add_argument("--fmt", 
                        default="xml",
                        help="Serialization format of the collection manifest.")
    parser.add_argument("--cache", 
                        default=None,
                        help="Name of file in which graph pickle is stored.")
    parser.add_argument("--store",
                        default=None,
                        help="Config file with all necessary params: host, dbname," +
                        " user, password, identifier, graph_uri," +
                        " plugin_name (optional)")
                        
    args = parser.parse_args()

    col_url = None
    if args.col_url or args.col_uri:
        col_url = __col_manifest_url(args)

    cache = load_cache(args.cache)
    g = cache['g']

    if col_url:
        fetch_and_parse(col_url, g, args.fmt, cache)
        qres = resource_urls(args.col_uri, g)
        for (res_url,) in qres:
            fetch_and_parse(res_url, g, args.fmt, cache)
    if args.res_url:
        fetch_and_parse(args.res_url, g, args.fmt, cache)
        res_uri = resource_uri(args.res_url, g)
        print "res_uri:", res_uri
        harvest_resource_triples(g, res_uri=res_uri, res_url=args.res_url, 
                                 cache=cache, fmt="xml")
        pages = pagination(g, collection_uri=args.col_uri, res_uri=res_uri,
                           cache=cache, fmt="xml")
        for p in pages:
            print p
    if args.find:
        harvest_resource_triples(g, collection_uri=args.col_uri, cache=cache, 
                                 pred="dc:title", obj=args.find, fmt="xml")
    elif args.pages:
        pages = pagination(g, collection_uri=args.col_uri, pred="dc:title", 
                           obj=args.pages, cache=cache, fmt="xml")
        for p in pages:
            print p
    else:
        if args.col_uri:
            list_resources(args.col_uri, g)
    
    save_cache(args.cache, cache)

