#-*- coding:utf-8 -*-
""" :mod:`cello.graphs.prox`
===========================

:copyright: (c) 2013 - 2014 by Yannick Chudy, Emmanuel Navarro.
:license: ${LICENSE}

.. currentmodule:: cello.graphs.prox

:hide:
    >>> from pprint import pprint

Python version of Prox over igraph.

Here is a minimal exemple:

>>> import igraph as ig
>>> graph = ig.Graph.Formula("a-b-c-d")   #TODO: avoir un 'Formula' a nous non depédendant de igraph
>>> prox_markov_dict(graph, [0], 2)
{0: 0.5, 2: 0.5}

On can also use a dict for `p0`:

>>> prox_markov_dict(graph, {0:1, 3:1}, 0)  # p0 is just normalized
{0: 0.5, 3: 0.5}
>>> prox_markov_dict(graph, {0:1, 3:1}, 1)
{1: 0.5, 2: 0.5}
>>> prox_markov_list(graph, {0:1, 3:1}, 1)
[0.0, 0.5, 0.5, 0.0]

Zachary :

>>> graph = ig.Graph.Famous("Zachary")
>>> p4 = prox_markov_dict(graph, [0], 4)
>>> len(p4)
34
>>> p4[0]
0.20139916513480394
>>> p4[2]
0.06625652318218955


There is also a MonteCarlo version :

>>> graph = ig.Graph.Formula("a-b-c-d")
>>> pprint(prox_markov_mtcl(graph, [0], 3, 20))            # doctest:+ELLIPSIS
{1: ..., 3: ...}

"""
import six
from past.builtins import basestring
from builtins import range

from random import randint
import numpy as np

import cello
from cello.graphs import IN, OUT, ALL

from reliure import Composable, Optionable
from reliure.types import Numeric, Boolean


class ProxExtract(Optionable):
    """ Proxsubgraph.
        return g' subgraph of g
        where ids are filtered by prox value.
        prox vector computed given a walk `length`, cut by nth first vertex
        random walks starts from `pzeros` [ vid, vid ... ] if none given pzeros is equiprobable on al vertices """
    
    def __init__(self, name=None, **kwargs):
        super(ProxExtract, self).__init__(name=name)
        options = [
        ("length", Numeric(vtype=int, default=3, min=1, help="random walk length")),
        ("cut", Numeric(vtype=int, default=100, min=1, help="vcount cut")),
        ("pzeros", Numeric(multi=True, uniq=True, vtype=int, default=[], min=0, help="pzero vertex index all if empty list or None")),
        ("add_loops", Boolean(default=True, help="add loops on vertices")),
        ("mode", Numeric(choices=[ IN, OUT, ALL], default=ALL, help="edge directions")),
        ("weighted", Boolean( default=True))
        ]
        for e,v in options: 
            self.add_option(e, v ) 
            if e in kwargs : self.set_option_value(e, kwargs[e])
            
    @Optionable.check
    def __call__(self, graph, length=3, cut=100, pzeros=None, weighted=True, add_loops=True, mode=ALL):
       
        # Extract n prox vertex
        weight = "weight" if weighted else None
        self._logger.info(  "length %s, cut %s, pzeros %s, weighted %s, add_loops %s, mode  %s" % (length, cut, pzeros, weighted, add_loops, mode))
        
        pzeros  = pzeros if  pzeros is not None and len(pzeros) else range(graph.vcount()) 
        
        extract = prox_markov_dict(graph, pzeros, length, mode=mode, add_loops=add_loops, weight=weight)
        subvs   = sortcut(extract,cut)
        return dict(subvs)


class ProxSubgraph(ProxExtract):
    def __init__(self, name=None, **kwargs):
        super(ProxSubgraph, self).__init__(name=name, **kwargs)
    
    @Optionable.check
    def __call__(self, graph, **kwargs):
        subvs = super(ProxSubgraph, self).__call__(graph, **kwargs)
        return graph.subgraph( subvs )
        
       

def normalise(p0):
    """ normalise p0 dict vector 

    :param p0: `dict` {vid: weight}.

    >>> p0 = {0: 1, 3: 1}
    >>> normalise(p0)
    {0: 0.5, 3: 0.5}
    """
    vsum = 1.* sum(abs(val) for val in six.itervalues(p0))
    return {vid: val/vsum for vid, val in six.iteritems(p0)}


def normalize_pzero(graph, p0):
    """ returns a normalised p0 dict.

    :param p0: `dict` {vid: weight} or `list` [vid, vid, ... ] weight is then 1 on each indicated vertex.

    >>> import igraph as ig
    >>> graph = ig.Graph.Formula("a--b--c")
    >>> normalize_pzero(graph, {1:0.5})
    {1: 1.0}
    >>> normalize_pzero(graph, {1: 0.5, 2: 1.5})
    {1: 0.25, 2: 0.75}
    >>> normalize_pzero(graph, [0, 1])
    {0: 0.5, 1: 0.5}
    
    If nothing given the start from all vertices :
    
    >>> normalize_pzero(graph, {})
    {0: 0.3333333333333333, 1: 0.3333333333333333, 2: 0.3333333333333333}
    >>> normalize_pzero(graph, [])
    {0: 0.3333333333333333, 1: 0.3333333333333333, 2: 0.3333333333333333}
    
    """
    if len(p0) == 0:
        p0 = range(graph.vcount()) # graph global
    if isinstance(p0, dict):
        vect = normalise(p0)
    else:
        vect = normalise({vid: 1. for vid in p0})
    return vect


def sortcut(v_extract, vcount):
    """ Gets the first vcount vertex sorted by score from the list or dict of score

    >>> sortcut({45:0.2, 180:0.08, 20:0.12, 21:0.102, 255:0.85, 12:0.0021}, 3) 
    [(255, 0.85), (45, 0.2), (20, 0.12)]
    >>> sortcut({45:0.2, 180:0.08, 20:0.12, 21:0.102, 255:0.85, 12:0.0021}, 0) 
    []
    >>> sortcut([0.02, 0.12, 0.82, 0.001, 0.18], 3)
    [(2, 0.82), (4, 0.18), (1, 0.12)]
    >>> sortcut([0.02, 0.12, 0.82, 0.001, 0.18], 0)
    []
    >>> sortcut([0.02, 0.12, 0.82, 0.001, 0.18], -5)
    [(2, 0.82), (4, 0.18), (1, 0.12), (0, 0.02), (3, 0.001)]

    :param v_extract: dict vertex_ids, value or list of values
    :param vcount: vertex count
    :return: a list of the form: `[(vid1, score), (vid2, score), ...]`
    """
    if type(v_extract) is list:
        v_extract = { i: v for i, v in enumerate(v_extract) }
    v_extract = [ (i,v) for i, v in   six.iteritems(v_extract) if v > 0.] #  sparce prox_vect : [(id, prox_value)]
    v_extract.sort(key=lambda x: x[1], reverse=True) # sorting by prox.prox_markov
    if vcount >= 0:
        v_extract = v_extract[:vcount]
    
    return v_extract


def spreading(graph, in_vect, mode, add_loops):
    """ Spread value of in_vect throw the graph.

    :param graph: subclass of :class:`.AbstractGraph`
    :param in_vect: input vector, a python dictionary: `{vertex_id:value, ...}`
    :param mode: given to neighboors, consider OUT links, IN links our ALL for both
    :param add_loops: if True do as if every vertex hold a self loop
                     (force the graph to be reflexif)
    :returns: output vector same format as in_vect

    >>> import igraph as ig
    >>> graph = ig.Graph.Formula("a--b--c")
    >>> spreading(graph, {1:1}, mode=OUT, add_loops=False)
    {0: 0.5, 2: 0.5}
    >>> spreading(graph, {1:1}, mode=OUT, add_loops=True)
    {0: 0.3333333333333333, 1: 0.3333333333333333, 2: 0.3333333333333333}

    also works for directed graphs:

    >>> graph = ig.Graph.Formula("a-->b-->c")
    >>> spreading(graph, {1: 1}, mode=OUT, add_loops=False)
    {2: 1.0}
    >>> spreading(graph, {1: 1}, mode=IN, add_loops=False)
    {0: 1.0}
    >>> spreading(graph, {1: 1}, mode=ALL, add_loops=False)
    {0: 0.5, 2: 0.5}

    With `add_loops=True` it add a loops **even if** there is already a loops:

    >>> graph = ig.Graph.Formula("a<->b<->c, b->b", simplify=False)
    >>> graph.neighbors(1, mode=OUT)
    [0, 1, 2]
    >>> spreading(graph, {1:1}, mode=OUT, add_loops=True)
    {0: 0.25, 1: 0.5, 2: 0.25}
    """
    vect = {}
    for vtx, value in six.iteritems(in_vect):
        neighborhood = graph.neighbors(vtx, mode=mode)
        if add_loops:
            neighborhood.append(vtx)
        if len(neighborhood) > 0:
            pvalue = 1. * value / len(neighborhood)
            for neighbor in neighborhood:
                vect[neighbor] = vect.get(neighbor, 0.) + pvalue
    return vect


def spreading_wgt(graph, in_vect, mode, weight, loops_weight):
    """ Spread value of in_vect throw the graph. (weighted version)
    
    :param graph: subclass of :class:`.AbstractGraph`
    :param in_vect: input vector, a python dictionary : {vertex_id:value, ...}
    :param mode: given to neighboors, consider OUT links, IN links our ALL for both
    :param weight: a list of weight (`|weight| == graph.ecount()`)
    :param loops_weight: list of weights for loops (if None then no loops)

    :returns: output vector same format as in_vect.


    >>> import igraph as ig
    >>> graph = ig.Graph.Formula("a--b--c")
    >>> weight = [3., 1.]
    >>> spreading_wgt(graph, {1:1.0}, mode=OUT, weight=weight, loops_weight=None)
    {0: 0.75, 2: 0.25}
    >>> spreading_wgt(graph, {0:2.0}, mode=OUT, weight=weight, loops_weight=None)
    {1: 2.0}

    also works for directed graphs:

    >>> graph = ig.Graph.Formula("a-->b-->c")
    >>> weight = [3., 1.]
    >>> spreading_wgt(graph, {1:1.0}, mode=OUT, weight=weight, loops_weight=None)
    {2: 1.0}
    >>> spreading_wgt(graph, {1:1.0}, mode=IN, weight=weight, loops_weight=None)
    {0: 1.0}
    >>> spreading_wgt(graph, {1:1.0}, mode=ALL, weight=weight, loops_weight=None)
    {0: 0.75, 2: 0.25}

    It is possible to force the graph to be reflexif and then to specify the 
    weight on each loop:
    >>> graph = ig.Graph.Formula("a-->b-->c")
    >>> weight = [3., 1.]
    >>> loops_weight = [0, 1., 2.]  # no loops on a, loops with weight 1 and 2 on b and c
    >>> spreading_wgt(graph, {1:1.0}, mode=OUT, weight=weight, loops_weight=loops_weight)
    {1: 0.5, 2: 0.5}
    >>> spreading_wgt(graph, {1:1.0}, mode=IN, weight=weight, loops_weight=loops_weight)
    {0: 0.75, 1: 0.25}
    >>> spreading_wgt(graph, {1:1.0}, mode=ALL, weight=weight, loops_weight=loops_weight)
    {0: 0.6, 1: 0.2, 2: 0.2}
    >>> spreading_wgt(graph, {0:0.5, 2:0.5}, mode=OUT, weight=weight, loops_weight=loops_weight)
    {1: 0.5, 2: 0.5}

    With `add_loops=True` it add a loops **even if** there is already a loops:

    >>> graph = ig.Graph.Formula("a<->b<->c, c->c", simplify=False)
    >>> weight = [3., 3., 1., 1., 2.]  # [a->b,  b->a, b->c, c->b, c->c]
    >>> loops_weight = [1., 1., 1.]    # [a->a, b->b, c->c]
    >>> graph.neighbors(2, mode=OUT)
    [1, 2]
    >>> spreading_wgt(graph, {2:1.0}, mode=OUT, weight=weight, loops_weight=loops_weight)
    {1: 0.25, 2: 0.75}
    """
    out_vect = {}
    es = graph.es    # get a ref to edge sequence
    add_loops = True if isinstance(loops_weight, list) else False

    if not isinstance(weight, list):
        raise TypeError
    if len(weight) != graph.ecount():
        raise NotImplementedError

    for from_vertex, value in six.iteritems(in_vect):
        incident_edges = graph.incident(from_vertex, mode=mode)
        wgts = [weight[edg] for edg in incident_edges]
        # add the loop weight
        loop_wgt = loops_weight[from_vertex] if add_loops else 0
        tot = 1. * sum(wgts) + loop_wgt
        if tot > 0:
            for i, edge in enumerate(incident_edges):
                target = es[edge].target
                neighbor = target if from_vertex != target else es[edge].source
                out_vect[neighbor] = out_vect.get(neighbor, 0.) + value * wgts[i] / tot
            if add_loops and loop_wgt > 0:
                out_vect[from_vertex] = out_vect.get(from_vertex, 0.) + value * loop_wgt / tot
    return out_vect




def prox_markov_dict(graph, p0, length, mode=OUT, add_loops=False, weight=None,
                        loops_weight=None, neighbors=None):
    """ Generic prox implementation

    For `p0`: it is either a list of vertex idx or a dict of vertex associated 
    with starting weight. If it is a list of vertex idx (`[id_vertex1, id_vertex2, ...]`)
    then the walk starts with equal probability on each of theses vertices.
    If it is a dict (`{id_vertex1:0.2, id_vertex2:0.5, ...}`) the the walk starts 
    on of theses vertices with a propability proportional to the associated score.

    :param graph: subclass of :class:`.AbstractGraph`
    :param p0: list of starting nodes (see above)
    :param length: random walk length
    :param mode: given to neighboors, consider OUT links, IN links our ALL for both
    :param add_loops: if True do as if every vertex hold a self loop
         (force the graph to be reflexif)
    :param weight: if None the graph is not weighting, else it could be:
        a str corresponding to an edge attribute to use as weight,
        or a list of weight (`|weight| == graph.ecount()`),
        or a callable `lambda graph, source, target: wgt`
    :param loops_weight: only if `add_loops`, weight for added loops, it may be:
        a str corresponding to a vertex attribute,
        or a list of weight (`|loops_weight| == graph.vcount()`),
        or a callable `lambda graph, vid, mode, weight: wgt`
    :param neighbors: function that override std graph.neighbors fct
    :returns: result vector, a python dictionary : `{vertex_id:value, ...}`
    
    For `neighbors_fct` you can use:

    neighbors_fct = lambda graph, from_vertex: graph.neighbors(from_vertex)
    neighbors_fct = ig.Graph.neighbors

    Without weights:

    >>> import igraph as ig
    >>> graph = ig.Graph.Formula("a--b--c")
    >>> prox_markov_dict(graph, [1], 2, add_loops=False)
    {1: 1.0}
    >>> graph = ig.Graph.Formula("a--b--c--a")
    >>> prox_markov_dict(graph, [0], 2, add_loops=False)
    {0: 0.5, 1: 0.25, 2: 0.25}
    >>> prox_markov_dict(graph, [0], 3, add_loops=True)
    {0: 0.3333333333333333, 1: 0.3333333333333333, 2: 0.3333333333333333}

    and with weights:

    >>> graph = ig.Graph.Formula("a--b--c")
    >>> graph.es["wgt"] = [3, 1]
    >>> prox_markov_dict(graph, [0], 2, add_loops=False, weight="wgt")
    {0: 0.75, 2: 0.25}
    >>> wgt_array = [1, 3]
    >>> prox_markov_dict(graph, [0], 2, add_loops=False, weight=wgt_array)
    {0: 0.25, 2: 0.75}
    >>> wgt_fct = lambda graph, edge: 2
    >>> prox_markov_dict(graph, [0], 2, add_loops=False, weight=wgt_fct)
    {0: 0.5, 2: 0.5}


    and with weights and loops:
    >>> get_weight = get_average_es_weight
    >>> # by default if you add loops they have the average weight of the other edges:
    >>> prox_markov_dict(graph, [0], 2, add_loops=True, weight="wgt")
    {0: 0.5, 1: 0.41666666666666663, 2: 0.08333333333333333}
    >>> # one can check that we have the same than:
    >>> prox_markov_dict(graph, [0], 2, add_loops=True, weight="wgt", loops_weight=get_weight)
    {0: 0.5, 1: 0.41666666666666663, 2: 0.08333333333333333}
    >>> prox_markov_dict(graph, [1], 2, add_loops=True, weight="wgt", loops_weight=get_weight)
    {0: 0.41666666666666663, 1: 0.4444444444444444, 2: 0.1388888888888889}
    >>> # but you can also give custom weight for loops:
    >>> prox_markov_dict(graph, [0], 2, add_loops=True, weight="wgt", loops_weight=[100, 10, 1])
    {0: 0.9488372406178044, 1: 0.049082315554179065, 2: 0.0020804438280166435}
    """

    vect = normalize_pzero(graph, p0)
    if neighbors is not None:
        raise NotImplementedError
    if weight is None:
        ## Not weighted version
        for k in range(length):
            vect = spreading(graph, vect, mode, add_loops)
    else:
        ## Weighted version
        # prepare the weights (if needed)
        if isinstance(weight, basestring):
            weight = graph.es[weight]
        elif callable(weight):
            weight = [weight(graph, edge ) for edge in graph.es]
        # prepare the weights for loops (if any)
        if add_loops:
            def lw(graph, idx, mode, w): # loop weight
                _w = get_average_es_weight (graph, idx, mode, w)
                return 1. if _w == 0.  else _w
            
            if isinstance(loops_weight, basestring):
                loops_weight = graph.vs[weight]
            elif isinstance(loops_weight, list) == False : 
                #defaut loop weight for each vertex is the average weight OUT/IN edges of the vertex.
                if not callable(loops_weight) :
                    loops_weight = lw
                        
                #compute the weight of incident edges for all vertices
                vs_incident = []
                for vtx in graph.vs : 
                    vs_incident.append([weight[edge] for edge in graph.incident(vtx.index, mode)])
                loops_weight = [loops_weight(graph, vtx.index, mode, vs_incident[vtx.index]) for vtx in graph.vs]

        else:
            loops_weight = None
        # compute prox it self
        for k in range(length):
            vect = spreading_wgt(graph, vect, mode, weight, loops_weight)
    return vect

def _wneighbors(graph, v ):
    """
    force refexiv & ALL edges weight 1
    ::
    """
    e = set([ e for e in graph.neighbors(v, mode=ALL) ] + [v])    
    return zip( list(e), [1.]*len(e) )
    
def pure_prox(graph, p0, length, wneighbors=None):
    

    if wneighbors == None:
        wneighbors = _wneighbors
        
    vect = normalize_pzero(graph, p0)
    for k in range(length):
        out_vect = {}
        #print vect
        for vid, value in six.iteritems(vect):
            neighbors = wneighbors(graph, vid)
            tot = 1. * sum([ w for v, w in neighbors ])
            if tot > 0:
                for v, w in neighbors:
                    out_vect[v] = out_vect.get(v, 0.) + value * w / tot
        vect = out_vect
    return vect


def prox_markov_list(graph, p0, length, mode=OUT, add_loops=False, loops_weight=None, weight=None,
                        neighbors=None):
    """ Same as :func:`prox_markov_dict` except that the output is a list of
    the order of the graph
    
    >>> import igraph as ig
    >>> graph = ig.Graph.Formula("a--b--c")
    >>> prox_markov_list(graph, {1:1}, 2, add_loops=False)
    [0.0, 1.0, 0.0]
    >>> prox_markov_list(graph, {1:1}, 11, add_loops=False)
    [0.5, 0.0, 0.5]
    >>> prox_markov_list(graph, {0:1}, 3, add_loops=True)
    [0.3472222222222222, 0.4305555555555555, 0.2222222222222222]
    >>> prox_markov_list(graph, {0:1}, 40, add_loops=True)
    [0.28571428571474045, 0.42857142857142855, 0.28571428571383095]
    """
    vect = prox_markov_dict(graph, p0, length, mode, add_loops, weight, loops_weight, neighbors)
    return [vect.get(vidx, 0.) for vidx in range(graph.vcount())]


def prox_markov_mtcl(graph, p0, length, throws, mode=OUT, add_loops=False, loops_weight=None,
                        weight=None, neighbors=None):
    """ Prox 'classic' by an approximate method montecarlo with nb_throw throws

    :param graph: graph in igraph format
    :param p0: list of starting nodes : [id_vertex1, id_vertex2, ...]
    :param length: random walk length
    :param nb_throw: the number of throws in montecarlo process
    :param mode: given to neighboors, consider OUT links, IN links our ALL for both
    :param add_loops: if True do as if every vertex hold a self loop
         (force the graph to be reflexif)
    :param weight: if None the graph is not weighted, else it could be:
        a str corresponding to an edge attribute to use as weight,
        or a list of weight (`|weight| == graph.ecount()`),
        or a callable `lambda graph, source, target: wgt`
    :param loops_weight: only if `add_loops`, weight for added loops, it may be :
        a str corresponding to a vertex attribute,
        or a list of weight (`|loops_weight| == graph.vcount()`),
        or a callable `lambda graph, vid, mode, weight: wgt`
    :param neighbors: function that override std graph.neighbors fct
    
    :returns: prox_vect, died: prox_vect is a python dictionary : {vertex_id:value, ...} AND died is the probability of dying during the random walks (the walker die when he has to do a step starting from a vertex without neighbors)
    """ 
    prox_vect = {} # le vecteur de proxemie approchée par montecarlo
    died = 0 # proba de mourir : on meurt qd on doit faire un pas a partir d'un sommet sans voisins
    #p0 = normalise(p0)
    
    if neighbors is None:
         neighbors= cello.graphs.neighbors

    if weight is not None:  #FIXME
        raise NotImplementedError
    
    for throw in range(throws) :
        neighborhood = list(normalize_pzero(graph, p0)) # FIXME not weighted
        for j in range(length) :
            len_n = len(neighborhood)
            if len_n  > 0 :
                vtx = neighborhood[randint(0, len_n-1)]
                neighborhood = neighbors(graph, vtx, mode)
                if add_loops and not vtx in neighborhood:
                    neighborhood.append(vtx)
        
        len_n = len(neighborhood)
        if len_n > 0 :
            vtx = neighborhood[randint(0, len_n -1)]
            if vtx in prox_vect:
                prox_vect[vtx] = prox_vect[vtx] + 1
            else :
                prox_vect[vtx] = 1
        else :
            died = died+1
    if died != 0:
        died = 1. * died/throws
    for k in prox_vect.keys():
        prox_vect[k] = 1. * prox_vect[k] / throws
    return prox_vect #, died


################################################################################

#TODO: do not put "cello.graphs.neighbors" in default but None and set it to cello.graphs.neighbors in the function
def confluence(graph, vtxa, vtxb, length=3, add_loops=True, remove_edge=False, 
            prox_markov_list=prox_markov_list, neighbors=cello.graphs.neighbors):
    """ Compute the confluence
    use prox_markov_list_c
    
    :param remove_edge: wheter to remove edge before computing similarity of an edge.
    """
    assert not graph.is_directed()
    
    # FIXME
    if remove_edge:
        raise NotImplementedError
    if not add_loops:
        raise NotImplementedError
        
    # default MODE is OUT
    # neighbors is not used 
    
    sim = prox_markov_list(graph, [vtxa], length=length, add_loops=add_loops)[vtxb]
    degree = np.array(graph.degree(), dtype=float) + 1.
    lsum = degree.sum()
    limit = (graph.degree(vtxb) + 1.) / lsum
    sim_init = sim
    sim /= (sim + limit)
    assert sim<=1., "cfl: %1.3f prox: %1.4f  limit=%1.5f  lsum: %1.6f" % (sim, sim_init, limit, lsum)
    return sim


def mean_confluence_simple(graph, p0, length=3, method=prox_markov_dict, **kwargs):
    conf = confluence_simple(graph, p0, length=3, method=prox_markov_dict, **kwargs)
    if len(conf):
        return sum(conf.values()) / len(conf)
    return None
    
def confluence_simple(graph, p0, length=3, method=prox_markov_dict, **kwargs):
    pm = method(graph, p0, length=length , **kwargs)
    neighbors = cello.graphs.neighbors
    conf =  { k: 1.*v / (v+(1.*len(neighbors(graph,k))/(2*graph.ecount()))) for k,v in six.iteritems(pm)}
    return conf



##########################################################################
def weight_one(graph, idx, mode=ALL, weight=None): return 1.

def get_average_es_weight(graph, idx, mode=ALL, weight=None):
    """ Compute the average weight of the edges that link the idx vertex to its neighbors

    :param graph: subclass of :class:`.AbstractGraph`
    :param idx: id of the vertex
    :param mode: given to neighboors, consider OUT links, IN links our ALL for both
    :param weight: if None the average_es_weight is 1 else:
        a str corresponding to an edge attribute to use as weight,
        or a list of weight (`|weight| == len(graph.incident(idx, mode=mode_int_to_str[mode]))`)
        
    >>> import igraph as ig
    >>> graph = ig.Graph.Formula("a--b--c")
    >>> graph.es["wgt"] = [3, 1]
    >>> get_average_es_weight(graph, 1)
    1.0
    >>> get_average_es_weight(graph, 1, weight="wgt")
    2.0
    >>> graph = ig.Graph.Formula("a-->b-->c-->d, b-->d")
    >>> graph.es["wgt"] = [3, 2, 1, 2]
    >>> get_average_es_weight(graph, 1, weight="wgt")
    2.0
    >>> get_average_es_weight(graph, 2, weight="wgt")
    2.0
    >>> get_average_es_weight(graph, 1, mode=OUT, weight="wgt")
    1.5
    >>> get_average_es_weight(graph, 1, mode=IN, weight="wgt")
    3.0
    >>> get_average_es_weight(graph, 1, mode=ALL, weight=[1, 4, 1])
    2.0
    >>> get_average_es_weight(graph, 1, mode=IN, weight=[3])
    3.0
    >>> get_average_es_weight(graph, 1, mode=OUT, weight=[1, 2])
    1.5
    >>> get_average_es_weight(graph, 1, mode=OUT, weight=[1, 4, 1])
    Traceback (most recent call last):
    ...
    ValueError: weight list should have the same lenght than vertex incidence list

    """
    if isinstance(weight, basestring):
        es = graph.incident(idx, mode)
        es_wgt = [graph.es[eid][weight] for eid in es]
        loop_weight = (1. * sum(es_wgt))/len(es_wgt) if len(es_wgt) > 0 else 1.
        
    elif isinstance(weight, list):
        if len(weight) != len(graph.incident(idx, mode)):
            raise ValueError("weight list should have the same lenght than vertex incidence list")
        loop_weight = 1. * sum(weight)/len(weight) if len(weight) > 0 else 1.
    elif callable(weight):
        es = graph.incident(idx, mode)
        es_wgt = [weight(graph, es[eid]) for eid in es]
        loop_weight = (1. * sum(es_wgt))/len(es_wgt) if len(es_wgt) > 0 else 1.
    else:
        loop_weight = 1.
        
    return loop_weight


