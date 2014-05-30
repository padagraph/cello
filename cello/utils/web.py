#-*- coding:utf-8 -*-
""" :mod:`cello.layout.web`
===========================

helpers to build HTTP/Json Api from cello engines
"""

import sys
import json

from collections import OrderedDict

from flask import Flask
from flask import Blueprint
from flask import abort, request, jsonify

from cello.types import GenericType, Text
from cello.exceptions import CelloPlayError
from cello.engine import Engine

# for error code see http://fr.wikipedia.org/wiki/Liste_des_codes_HTTP#Erreur_du_client


class CelloFlaskView(Blueprint):
    """ Standart Flask json API view over a Cello :class:`.Engine`.

    This is a Flask Blueprint.
    """

    def __init__(self, engine):
        """ Build the Blueprint view over a :class:`.Engine`.
        
        :param engine: the cello engine to serve through an json API
        :type engine: :class:`.Engine`.
        """
        super(CelloFlaskView, self).__init__("cello", __name__)
        self.engine = engine
        # default input
        self._inputs = OrderedDict()
        # default outputs
        self._outputs = OrderedDict()
        
        # bind entry points
        self.add_url_rule('/options', 'options', self.options)
        self.add_url_rule('/play', 'play', self.play,  methods=["POST", "GET"])

    def set_input_type(self, type_or_parse):
        """ Set an unique input type.
        
        If you use this then you have only one input for the play.
        """
        self._inputs = OrderedDict()
        default_inputs = self.engine.in_name
        if len(default_inputs) > 1:
            raise ValueError("First block of the engine need more than one input, you sould use `add_inpout` for each of them")
        self.add_input(default_inputs[0], type_or_parse)

    def add_input(self, in_name, type_or_parse):
        """ declare a possible input
        """
        if not isinstance(type_or_parse, GenericType) and callable(type_or_parse):
            type_or_parse = GenericType(parse=type_or_parse)
        elif not isinstance(type_or_parse, GenericType):
            raise ValueError("the given 'type_or_parse' is invalid")
        self._inputs[in_name] = type_or_parse

    def add_output(self, out_name, serializer=None):
        """ declare an output
        """
        if serializer is not None and not callable(serializer):
            raise ValueError("the given 'serializer' is invalid")
        self._outputs[out_name] = serializer

    def options(self):
        """ Engine options discover HTTP entry point
        """
        conf = self.engine.as_dict()
        #TODO add possible inputs
        conf["returns"] = [oname for oname in self._outputs.iterkeys()]
        conf["args"] = [iname for iname in self._inputs.iterkeys()]
        return jsonify(conf)

    def play(self):
        """ play HTTP entry point
        """
        if not request.headers['Content-Type'].startswith('application/json'):
            abort(415) # Unsupported Media Type
        ### get data
        data = request.json
        assert data is not None #FIXME: better error than assertError ?
        #
        ### parse options
        if "options" in data:
            options = data["options"]
            try:
                self.engine.configure(options)
            except ValueError as err:
                #TODO beter manage input error: indicate what's wrong
                abort(406)  # Not Acceptable
        ### Check inputs
        needed_inputs = self.engine.needed_inputs()
        # check if all needed inputs are possible
        if not all([inname in self._inputs for inname in needed_inputs]):
            #XXX this may be check staticly
            raise NotImplementedError()
        # check if all inputs are given
        if not all([inname in data for inname in needed_inputs]):
            #XXX ERROR should be handle
            raise NotImplementedError()
        #
        ### parse inputs (and validate)
        inputs_data = {}
        for inname in needed_inputs:
            input_val = self._inputs[inname].parse(data[inname])
            self._inputs[inname].validate(input_val)
            inputs_data[inname] = input_val
        #
        ### run the engine
        error = False #by default ok
        try:
            raw_res = self.engine.play(**inputs_data)
        except CelloPlayError as err:
            # this is the cello error that we can handle
            error = True
        finally:
            pass
        #
        ### prepare outputs
        outputs = {}
        results = {}
        if not error:
            # prepare the outputs
            for out_name, raw_out in raw_res.iteritems():
                if out_name not in self._outputs:
                    continue
                serializer = self._outputs[out_name]
                # serialise output
                if serializer is not None:
                    results[out_name] = serializer(raw_res[out_name])
                else:
                    results[out_name] = raw_res[out_name]
        ### prepare the retourning json
        # add the results
        outputs["results"] = results
        ### serialise play metadata
        outputs['meta'] = self.engine.meta.as_dict()
        #note: meta contains the error (if any)
        return jsonify(outputs)

