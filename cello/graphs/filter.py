#-*- coding:utf-8 -*-
""" :mod:`cello.graphs.filter`
==============================
"""
import itertools

from cello.pipeline import Optionable
from cello.types import Numeric

class BottomFilter(Optionable):
    """ Removes bottom (type=False) vertices from a bigraph.
    """
    #TODO add doc test
    def __init__(self):
        name = self.__class__.__name__
        Optionable.__init__(self, name)

        self.add_option("top_min", Numeric(default=0, min=0.,
            help="Removes type=False vertices connected to less than top_min (type=True) vertices"))
        self.add_option("top_max_ratio", Numeric(vtype=float, default=1., min=0., max=1.,
            help="Removes type=False vertices connected to more than top_max_ratio percents of the (type=True) vertices"))

    #XXX:kwargs ne sert a rien ?
    def __call__(self, graph, top_min=0, top_max_ratio=1., **kwargs):
        """remove bottoms (type false) vertices, that are not enought connected
        or too much connected.

        :param top_min: removes v[false] if degree(g, v[false]) <= top_min
        :type top_min: int
        :param top_max_ratio: removes `v` (type=false) if `degree(g, v) >= top_max_ratio * |V_top|`
        :type top_max_ratio: float
        """
        assert graph.is_bipartite();

        top_count = len(graph.vs.select(type=True))
        
        self._logger.info("Before filtering: |V_top docs|=%d, |V_bottom terms|=%d, |E|=%d"\
             % (len(graph.vs.select(type=True)), len(graph.vs.select(type=False)), graph.ecount()))
        
        too_poor_bots = graph.vs.select(type=False, _degree_le=top_min)
        
        self._logger.info("%d bottoms have less than %s neighbors, will be deleted" % (len(too_poor_bots), top_min))
        
        too_rich_bots = graph.vs.select(type=False, _degree_gt=top_max_ratio * top_count)
        
        self._logger.info("%d bottoms have more than %s neighbors (%1.2f * %d), will be deleted"\
             % (len(too_rich_bots), top_max_ratio * top_count, top_max_ratio, top_count))
        
        graph.delete_vertices(itertools.chain(too_poor_bots, too_rich_bots))
        
        self._logger.info("After filtering: |V_top|=%d, |V_bottom|=%d, |E|=%d" \
            % (len(graph.vs.select(type=True)), len(graph.vs.select(type=False)), graph.ecount()))
        return graph