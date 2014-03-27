#-*- coding:utf-8 -*-
""" :mod:`cello.clustering`
===========================
"""

import logging

import igraph as ig

from cello.clustering.core import OneCluster, ConnectedComponents, MaximalCliques
from cello.clustering.common import Walktrap, Infomap

from cello.clustering.filter import basic_cover_filter

#{ Pack of methods

def unipartite_clustering_methods():
    """ Returns standart clustering method for unipartite graphs
    """
    methods = []
    methods.append(Infomap() | basic_cover_filter())
    methods.append(Walktrap() | basic_cover_filter()    )
    return methods


def bipartite_clustering_methods():
    """ Returns standart clustering method for bipartite graphs
    """
    methods = []
    methods.append(Infomap())
    return methods


def export_clustering(vertex_cover):
    """ Build a dictionary view of a vertex cover (a clustering)
    
    .. Note:: for each cluster 'docnums' are extracted from vertices that have a
    (not None) '_doc' attribute
    
    .. code-block:: js
    
        {
            'misc': -1,
            'clusters': [
                {
                    'gids': [1, 3, 5, 8],
                    'docnums': [u'docnum_1', ...]
                },
                ...
            ]
        }
    :param vertex_cover: the vertex cover to convert
    :type vertex_cover: :class:`igraph.VertexCover`
    
    >>> from pprint import pprint
    >>> g = ig.Graph.Formula("a--b, a--c, a--d, a--f, d--f")
    >>> from cello.schema import Doc
    >>> g.vs["_doc"] = [Doc(docnum="d_%d" % vid) if vid%2 == 0 else None for vid in range(g.vcount())]

    >>> from cello.clustering import MaximalCliques
    >>> clustering = MaximalCliques()
    >>> cover = clustering(g)
    >>> cover_dict = export_clustering(cover)
    >>> pprint(cover_dict)
    {'clusters': [{'docnums': ['d_0', 'd_4'], 'vids': [0, 3, 4]},
                  {'docnums': ['d_0', 'd_2'], 'vids': [0, 2]},
                  {'docnums': ['d_0'], 'vids': [0, 1]}],
     'misc': -1}
    """
    cover = {}
    if hasattr(vertex_cover, "misc_cluster") : # "misc" cluster id
        cover['misc'] = vertex_cover.misc_cluster
    else: # pas de "misc"
        cover['misc'] = -1

    gid_to_doc = None
    if hasattr(vertex_cover, 'graph') and '_doc' in vertex_cover.graph.vs.attributes():
        gid_to_doc = {gid: doc.docnum \
            for gid, doc in enumerate(vertex_cover.graph.vs['_doc']) \
            if doc is not None
        }

    clusters = []
    for cnum, vids in enumerate(vertex_cover):
        cluster = {}
        cluster['vids'] = vids
        # doc ?
        cluster['docnums'] = []
        if gid_to_doc:
            cluster['docnums'] = [gid_to_doc[gid] for gid in vids if gid in gid_to_doc]
        # add the cluster
        clusters.append(cluster)
    cover['clusters'] = clusters
    return cover


