#-*- coding:utf-8 -*-
""" :mod:`cello.providers.es`
=============================

Set of class to acces a Elastic Search server
"""

import os.path
import logging

import elasticsearch
import elasticsearch.helpers as ESH


from cello.types import Numeric, Text

from cello.pipeline import Composable, Optionable
from cello.index import Index, CelloIndexError
from cello.search import AbstractSearch


class EsIndex(Index):
    """ Elasticsearch index for a particular doc_type
    """

    def __init__(self, index, doc_type="document", schema=None, settings=None, es=None, host=None):
        """

        :param index: index name
        :param doc_type: the name of document type to use
        :param schema: schema of documents
        :param settings: index settings / analysers 
        :param es: initialised Elastic Search python client :class:`elasticsearch.Elasticsearch` (if None one is created with given host)
        :param host: base url for connection
        """
        #TODO: wrap param
        Index.__init__(self)
        # FIXME raise error
        assert es is not None or host is not None, "'es' or 'host' should be given"
        # create a connection to a es server and retrive mapping and  uniq key
        if es is None:
            self._es = elasticsearch.Elasticsearch(hosts=host)
        else:
            self._es = es
        self.index = index
        self.doc_type = doc_type
        self.schema = schema
        self.settings = settings
        #TODO: ensure there is a docnum in the schema, and _id path to it ?

    def __len__(self):
        """ return count of document in index """
        res = self._es.count(self.index, doc_type=self.doc_type)
        return res["count"]

    def __contains__(self, key):
        """
        True if index has document with `key`
        """
        return self.has_document(key)
    
    
    
    def get(self, key, default=None):
        item = self.__getitem__(key)
        return item if item is not None else default

    def __getitem__(self, key):
        return self.get_document(key)

    def __setitem__(self,  key, document):
        uniqkey = self.get_uniq_key()
        
        if document is  None: 
            raise ValueError("document cant be 'None'")
        if uniqkey is None:
            raise ValueError("Can t use setitem if index has no uniq key")
        if key != document[uniqkey]:
            raise ValueError( "key should match uniqkey value in document %s != %s" % ( key, document[uniqkey] ))   

        self.add_document(document)


    def __iter__(self):
        uniqkey = self.get_uniq_key()
        scan = ESIndexScan(self)
        # todo check doc_type
        for doc in scan(None):
            key = doc['_source'][uniqkey]
            yield uniqkey, doc['_source']

    def iteritems(self):
        return iter(self)

    def iterkeys(self):
        for k, v in iter(self):
            yield k
            
    def itervalues(self):
        for k, v in iter(self):
            yield v
            
    def iter_docnums(self, incr=1000):
        return self.iterkeys()

    def refresh(self):
        """ Make sure that all current operation are available for search
        """
        if self.exist():
            self._es.indices.refresh(self.index)

    def statistics(self):
        return {
            "ndocs": len(self)
        }

    def exist(self):
        """ True if index and doctype mapping exists
        """
        if self._es.indices.exists(self.index):
            mappings = self._es.indices.get_mapping(index=self.index)
            return self.index in mappings and self.doc_type in mappings[self.index]['mappings']
        else:
            return False

    def create(self):
        """ Create the index, and add the doc type schema (if given)
        """
        if self.exist():
            raise RuntimeError("Index already exist !")
        body = {}
        if not self._es.indices.exists(self.index):
            if self.settings is not None:
                body["settings"] =  self.settings
            body["mappings"] = {}
            body["mappings"][self.doc_type] = {}
            if self.schema is not None:
                body["mappings"][self.doc_type] = self.schema
            self._logger.info("Create the index")
            self._es.indices.create(self.index, body=body)
        else:
            if self.schema is not None:
                body[self.doc_type] = self.schema
                self._logger.info("Add a mapping (Index already exist)")
                self._es.indices.put_mapping(index=self.index, doc_type=self.doc_type, body=body)
            if self.settings is not None:
                self._logger.warn("Settings where not updated (Index already exist)")

    def delete(self, full=False):
        """ Remove the index from ES instance
        """
        mappings = self._es.indices.get_mapping(index=self.index)
        if not full and self.index in mappings:
            if self.doc_type in mappings[self.index]['mappings'] and len(mappings[self.index]['mappings']) > 1:
                # More than one doctype, only delete mine !
                self._logger.info("Remove just the mapping")
                self._es.indices.delete_mapping(self.index, doc_type=self.doc_type, ignore=400)
            elif self.doc_type in mappings[self.index]['mappings']:
                self._logger.info("Remove the full index")
                self._es.indices.delete(self.index, ignore=400)
        else: # delete the whole index
            self._logger.info("Remove the full index")
            self._es.indices.delete(self.index, ignore=400)

    def get_mapping(self):
        """ Get the mapping (or schema) for the current doc_type in the index
        """
        mappings = self._es.indices.get_mapping(index=self.index, doc_type=self.doc_type)
        if self.index in mappings and self.doc_type in mappings[self.index]['mappings']:
            return mappings[self.index]['mappings'][self.doc_type]
        else:
            return {}

    def get_uniq_key(self):
        """ return the field used as _id
        """
        uniq_key = None
        mapping = self.get_mapping()
        if '_id' in mapping and 'path' in mapping['_id']:
            uniq_key = mapping['_id']['path']
        return uniq_key

    def get_fields(self):
        """ Returns field names declared in the schema as a list """
        return self.get_mapping()['properties'].keys()

    def has_document(self, docnum):
        """Test for a document in Index.  Fetchs document and returns True wether exists """
        return self.get_document(docnum) is not None

    def get_document(self, docnum, **kwargs):
        """ fetch a document given a docnum 
        it will match the given value in field specified as 'uniqueKey' in schema
        """
        docs = list(self.get_documents([docnum], **kwargs))
        return docs[0] if len(docs) else None

    def get_documents(self, docnums, **kwargs):
        """ fetch a set of documents given a docnum list or iterator.
        it will match the given value in field specified as 'uniqueKey' in schema
        """
        body = {'ids': docnums}
        docs = self._es.mget(index=self.index, doc_type=self.doc_type, body=body, **kwargs)
        docs = list(doc["_source"] for doc in docs["docs"] if doc["found"])
        return docs

    def add_document(self, doc):
        #TODO: ensure there is a docnum ?
        res = self._es.index(index=self.index, doc_type=self.doc_type, body=doc)
        return res

    def add_documents(self, docs):
        id_field = self.get_uniq_key()
        index = self.index
        doc_type = self.doc_type
        actions = [{
            #"_op_type": "index",
                        # ^ create, index, update are possible but
            '_index': index,
            '_type': doc_type,
            '_id': doc[id_field],
            "_source": doc,
        } for doc in docs]
        res = ESH.bulk(client=self._es, actions=actions)
        #TODO add error check on res !
        #res = ESH.bulk_index(client=self._es, actions=docs)
        return res

    def update_document(self, doc):
        """ Partial update a document.
        """
        self.update_documents((doc, ))

    def update_documents(self, docs, add_if_new=False):
        """ Partial update a list of documents.
        Only the field present will be updated.

        :param docs: a list of document
        """
        id_field = self.get_uniq_key()
        self._logger.debug("Use field : '%s' as _id field" % id_field)
        #TODO add a check id field exist on each doc
        index = self.index
        doc_type = self.doc_type
        if add_if_new:
            # get which document exist
            body = {'ids': [doc[id_field] for doc in docs]}
            res = self._es.mget(index=self.index, doc_type=self.doc_type, body=body, _source=False)
            found = [doc["found"] for doc in res["docs"]]
            actions = []
            for num, doc in enumerate(docs):
                doc_action = {
                    '_index': index,
                    '_type': doc_type,
                    '_id': doc[id_field],
                }
                if found[num]:
                    doc_action["_op_type"] = "update"
                    doc_action["doc"] = doc
                else:
                    doc_action["_source"] = doc
                actions.append(doc_action)
        else:
            actions = [{
                "_op_type": "update",
                            # ^ create, index, update are possible but
                '_index': index,
                '_type': doc_type,
                '_id': doc[id_field],
                "doc": doc,
            } for num, doc in enumerate(docs)]
        ESH.bulk(self._es, actions=actions)


class ESIndexScan(Composable):
    """ produce a generator over all documents of a :class:`ESIndex`
    """
    def __init__(self, es_index):
        super(ESIndexScan, self).__init__()
        self.es_index = es_index
        self._es = self.es_index._es

    def __call__(self, query):
        self._logger.debug("Start scan with query: %s" % query)
        for doc in ESH.scan(self._es, query=query, scroll='5m', index=self.es_index.index, doc_type=self.es_index.doc_type):
            yield doc


class ESQueryStringBuilder(Optionable):
    """ Create a json query for :class:`ESSearch`
    
    >>> qbuilder = ESQueryStringBuilder()
    >>> qbuilder.print_options()
    operator (Text, default=OR, in: {AND, OR}): operator used for chaining terms
    fields (Text, default=_all): List of fields 
                and the 'boosts' to associate with each of them. The format
                supported is "fieldOne^2.3 fieldTwo fieldThree^0.4", which indicates
                that fieldOne has a boost of 2.3, fieldTwo has the default boost, 
                and fieldThree has a boost of 0.4 ...
    >>> qbuilder("cat")
    {'query_string': {'query': 'cat', 'default_operator': u'OR', 'fields': [u'_all']}}
    >>> qbuilder("cat", operator=u'AND')
    {'query_string': {'query': 'cat', 'default_operator': u'AND', 'fields': [u'_all']}}
    """
    #TODO: add docstring
    def __init__(self, name=None):
        super(ESQueryStringBuilder, self).__init__(name=name)
        self.add_option("operator", Text(choices=[u"AND", u"OR",], default=u"OR",
            help=u"operator used for chaining terms"))
        self.add_option("fields", Text(default=u"_all", help=u"""List of fields 
            and the 'boosts' to associate with each of them. The format
            supported is "fieldOne^2.3 fieldTwo fieldThree^0.4", which indicates
            that fieldOne has a boost of 2.3, fieldTwo has the default boost, 
            and fieldThree has a boost of 0.4 ...""")
       )

    @Optionable.check
    def __call__(self, query, fields=None, operator=None):
        query_dsl = {
            "query_string": {
                "query": query,
                "fields": fields.split(),
                "default_operator": operator,
            }
        }
        return query_dsl


class ESSearch(Optionable):
    #TODO: add docstring ? not easy with ES connection
    def __init__(self, index=None, doc_type=None, host="localhost:9200", name=None):
        """
        :param index: index name
        :param doc_type: document type to search, if list of str then option will be added, if None
        :param host: ES hostname
        :param name: component name
        """
        super(ESSearch, self).__init__(name=name)
        self.add_option("size", Numeric(vtype=int, default=10, min=0, help="number of document to returns"))
        # configure ES connection
        self.host = host
        self._es_conn = elasticsearch.Elasticsearch(hosts=self.host)
        if not self._es_conn.ping():
            raise RuntimeError("Couldn't ping ES server at '%s'" % self.host)
        self.index = index
        # manage doctype: add an option if needed
        self.doc_type = None
        if isinstance(doc_type, basestring):
            # only one doctype
            self.doc_type = doc_type
        else:
            if doc_type is None:
                # fetch all the existing doctype
                mappings = self._es_conn.indices.get_mapping(index=self.index)
                doc_type = mappings[self.index]['mappings'].keys()
            if len(doc_type):
                self.add_option("doc_type", Text(multi=True, choices=doc_type,
                    default=doc_type, help="Documents type"))
            else:
                # if empty list no option, no doctype selection
                self.doc_type = None

    @Optionable.check
    def __call__(self, query_dsl, doc_type=None, size=None):
        self._logger.info("query: %s" % query_dsl)
        body = {
            "query": query_dsl,
        }
        dtype = None
        if isinstance(doc_type, (list, tuple)):
            dtype = ",".join(doc_type)
        elif doc_type is None and self.doc_type is not None:
            dtype = self.doc_type
        return self._es_conn.search(index=self.index, doc_type=dtype, body=body, size=size)


class ESPhraseSuggest(Optionable):
    #TODO: add docstring ? not easy with ES connection
    def __init__(self, index=None, host="localhost:9200", name=None):
        super(ESPhraseSuggest, self).__init__(name=name)
        # configure ES connection
        self.host = host
        self._es_conn = elasticsearch.Elasticsearch(hosts=self.host)
        if not self._es_conn.ping():
            raise RuntimeError("Imposible to ping ES server at '%s'" % self.host)
        self.index = index

    @Optionable.check
    def __call__(self, text):
        self._logger.info("text: %s" % text)
        size = 3 #number of proposition
        body = {
            "text": text,
            "simple_phrase": {
                "phrase": {
                    "field": "intro",
                    "size": size,
                    "real_word_error_likelihood": 0.95,
                    "max_errors": 0.5,
                    "gram_size": 1,
                    "direct_generator": [{
                        "field": "intro",
                        "suggest_mode": "always",
                        "min_word_length": 1
                    }],
                    "highlight": {
                        "pre_tag": "<em>",
                        "post_tag": "</em>"
                    }
                }
            }
        }
        return self._es_conn.suggest(index=self.index, body=body)

#---

#class EsSearch(AbstractSearch):
#    """ Make a search using ElasticSearch """
#    QF = u"title^5 redirects^3 text"

#    def __init__(self, host="http://localhost:9200", idx=None, doc_type=None, lang=None, connect=True, name=None):
#        name = name or __name__
#        super(AbstractSearch, self).__init__(name)
#        self._logger = logging.getLogger(name)
#        self.es_index = EsIndex(index=idx, host=host)
#        self._es_host = host
#        self._es_idx = idx
#        self._es_doctype = doc_type
#        self._lang = lang
#        
#        if connect:
#            assert idx is not None, "No Index provided"
#            assert lang is not None, "No lang  provided"
#         
#        # FIXME
##        self.add_bool_option("in_title", True, "Search in titles")
##        self.add_bool_option("in_redirects", True, "Search in redirects")
##        self.add_option("fl", '*,score', "fields returned by solr; &fl=", str)
#        self.add_option("doc_count", Numeric(default=10, help=u"Number of results; &rows="))
#        self.add_option("operator", Text(choices=[u"AND", u"OR",], default=u"AND", 
#            help=u"operator used for chaining terms"))
#        if connect:
#            fields = sorted(self.es_index.get_fields(doc_type))
#            self.add_option("search_field",
#                            Text(choices=[u"*"] + [unicode(e) for e in fields],
#                            default=u"*", help=u"field to search")
#                            )
#        else:
#            self.add_option(
#                    "search_field", Text(default=u"text", 
#                        help=u"""field to search for matching term.
#                         If '*' one can set the boosts per field in the @param qf.""",
#                ))

#        self.add_option(
#                    "qf", Text(default=EsSearch.QF, help=u"""List of fields 
#                    and the 'boosts' to associate with each of them when building
#                    DisjunctionMaxQueries from the user's query. The format supported 
#                    is fieldOne^2.3 fieldTwo fieldThree^0.4, which indicates that
#                    fieldOne has a boost of 2.3, fieldTwo has the default boost, 
#                    and fieldThree has a boost of 0.4 ... : &qf=""")
#               )

#    def __call__(self, query, search_field=u'text', qf=QF, fl=u"", doc_count=10, operator=u"AND", raw=False):
#        """ Perform a search using the Elasticsearch
#        :param search_field: field to search for matching term. 
#          If '*' one can set the boosts per field in the @param qf.
#        :param nb_res: max count of document to be returned
#        :param qf : List of fields and the 'boosts' to associate with each fields,
#          when building DisjunctionMaxQueries from the user's query. 
#          The format supported is fieldOne^2.3 fieldTwo fieldThree^0.4, indicates
#          that fieldOne has a boost of 2.3, fieldTwo has the default boost, and 
#          fieldThree has a boost of 0.4 ... : &qf=
#          this param will be used IF and ONLY `search_field` is '*'.
#          When qf is used &defType=dismax should be set
#        """
#        self._logger.info("query: '%s'" % query)
#        idx = self._es_idx
#        doc_type = self._es_doctype
#        kdocs = []

#        get_by_id = self.es_index.get_uniq_key(doc_type) == search_field

#        if not get_by_id:
#            if search_field == "*":
#                query_string = { 
#                        "query": query,
#                        "fields": qf.split(" "),
#                        "use_dis_max": True
#                        }
#            else:
#                query_string = {
#                        "query": query,
#                        "default_field": search_field,
#                        }
#            query_dsl = {
#                    "size": doc_count,
#                    "query": {
#                        "query_string": query_string
#                        }
#                    }

#        if query:
#            if get_by_id:
#                if type(query) not in (set, list, tuple):
#                    query = [query]
#                res = self.es_index._es.mget(index=idx, doc_type=doc_type, body={'ids': query})
#                retrieved = [d for d in res["docs"] if d["found"]]
#                for rank, doc in enumerate(retrieved):
#                    kdocs.append(self.to_doc(doc, rank+1))
#            else:
#                result = self.es_index._es.search(self._es_idx, doc_type=self._es_doctype, body=query_dsl)
#                if result["hits"]["total"] > 0:      
#                    for rank, doc in enumerate(result["hits"]["hits"]):
#                        if raw == False:
#                            kdoc = self.to_doc(doc, rank+1)
#                        else:
#                            kdoc = doc
#                        kdocs.append(kdoc)
#        return kdocs

#    def to_doc(self, doc, rank):
#        raise NotImplementedError
