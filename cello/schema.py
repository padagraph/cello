#-*- coding:utf-8 -*-
""" :mod:`cello.schema`
======================

:copyright: (c) 2013 - 2014 by Yannick Chudy, Emmanuel Navarro.
:license: ${LICENSE}


TODO

schema ds doc doit pas etre une key
attrs={'a':Numeric(multi=True, default=1)} )) ne gere pas les postings
DocField => DocContainer 
rename _field => _ftype

clean notebook in progress
"""


"""
    Errors  
"""
class SchemaError(Exception):
    pass

"""
    Main Schema class inspired from Matt Chaput's Whoosh.  
"""
class Schema(object):
    """
    Schema definition for docs <Doc>
    
    Creating a schema :
        >>>schema = Schema(**{ 'title': Text(), 'score':Numeric(numtype=int, multi=True) })
        >>># or
        >>>schema = Schema( title=Text(), score=Numeric() )
        >>>schema.field_names()
        >>># ['score', 'title']
        """
    
    def __init__(self, **fields):
        self._fields = {}
        
        for name,fieldtype in fields.iteritems():
            self.add_field(name, fieldtype)
        
    def add_field(self, name, field):
        """s
            Add a named field to the schema.
            :param name : name of the new field
            :param field : FieldType instance for the field 
        """
        # testing names 
        if name.startswith("_"):
            raise SchemaError("Field names cannot start with an underscore")
        if " " in name:
            raise SchemaError("Field names cannot contain spaces")
        
        if name in self._fields: 
            raise SchemaError("Schema already has a field named '%s'" %s)
        if isinstance(field, FieldType) == False:
            raise SchemaError("Wrong FieldType in schema for field :%s, v" % (name, field ) )
        self._fields[name] = field
    
    def remove_field(self, field_name):
        raise NotImplementedError()
        
    def iter_fields(self):
        return self._fields.iteritems()
    
    def field_names(self):
        return self._fields.keys()
    
    def has_field(self, name):
        return name in self._fields
    
    def __len__(self): 
        """ returns field count in schema """
        return len(self._fields)
    
    def __getattr__(self, name): 
        return self.__getitem__(name)
        
    def __getitem__(self, name): 
        if name == '_fields':
            
            return self._fields
        elif name in self._fields:
            return self._fields[name]
        else : 
            raise SchemaError("Field '%s' does not exist in Schema (%s)" % (name, self.field_names()))
    
    def __repr__(self):
        return "<%s: %s>"%( self.__class__.__name__, self._fields)


"""
   * FieldTypes to declare in schemas 
"""
class FieldType(object):
    """
    Abstract FieldType
    """
    def __init__(self, multi=False, uniq=False, default=None, attrs=None):
        """
        :param multi: field is a list or a set
        :param uniq: wether the values are unique. only apply if multi == True-
        :param default: default value for the field
        :param attrs: field attributes name: FieldType
        """
        self.multi = multi 
        self.uniq = uniq
        self.default = default
        self.attrs = attrs
        
        # TODO
        # self.sorted = sorted
        # self.required = required  # test ds Doc ds le constructeur
    
    
    def __repr__(self):
        temp = "%s(multi=%s, uniq=%s, default=%s, attrs=%s)"
        return temp % (self.__class__.__name__,
                    self.multi, self.uniq, self.default, self.attrs )
    
    def validate(self, value):
        pass

class Numeric(FieldType):
    _types_ = [int, float]
    
    def __init__(self, numtype=int, **field_options):
        """
        :param numtype: the type of numbers that can be stored in this field,
            either ``int``, ``float``. 
        """
        FieldType.__init__(self, **field_options)
        if numtype not in Numeric._types_  : 
            raise ValueError('Wrong type for Numeric %s' % Numeric._types_ )
        self.numtype = numtype
        
    def validate(self, value):
        if isinstance(value, self.numtype) == False :
            raise TypeError("Wrong type '%s' should be '%s'" % (type(value), self.numtype ))
        return value
   
class Text(FieldType):
    """
        
    """
    # valid type for text
    _types_ = [str, unicode]
    
    def __init__(self,texttype=str, **field_options):
        FieldType.__init__(self, **field_options)
        if texttype not in Text._types_  : 
            raise SchemaError('Wrong type for Numeric %s' % Numeric._types_ )
        self.texttype = texttype
        
    def validate(self, value):
        if isinstance(value, self.texttype) == False :
            raise TypeError("Wrong type '%s' should be '%s'" % (type(value), self.texttype ))
        return value



# Add more FiledType here

# ...
# ...

"""
Document fields implementations 
"""
class DocField(object):
    def __init__(self, fieldtype):
        self._field = fieldtype
        
    def get_value(self): pass

class ValueField(DocField):
    """
    Store only one value of FieldType
    """
    def __init__(self, fieldtype):
        DocField.__init__(self, fieldtype)
        self.value = fieldtype.default
    
    def get_value(self): 
        return self.value
    
    def set(self, value): 
         self.value = self._field.validate(value)

class SetField(DocField):
    """
        
        usage: 
            doc.schema.add_fields(tags=Text(multi=True, uniq=True) )
            doc.tags # SetField
            doc.tags.add('boo')
            doc.tags.add('foo')
            doc.tags # >>> ['boo', 'foo']
            
    """
    def __init__(self, fieldtype):
        DocField.__init__(self, fieldtype)
        self.value = None
        self.set(fieldtype.default or [])
    
    def get_value(self):
        return  list(self.value)
    
    def add(self, value):
        self.add( self._field.validate(value) )

    def set(self, values):
        if type(values) == list:
            self.value = set([ self._field.validate(v) for v in values ])
        else:
            raise SchemaError("Wrong value '%s' for field 's'" % (values, self._field))

    def __iter__(self):
        """ iterator over values """
        return iter(self.value)
        
class ListField(DocField):
    def __init__(self, fieldtype):
        DocField.__init__(self, fieldtype)
        self.value = [] 
    
    def get_value(self):
        return self.value
    
    def add(self, value):
        self.value.append( self._field.validate(value) )
        
    def set(self, value):
        if type(value) == list:
            self.value = [ self._field.validate(v) for v in value ]
        else:
            raise SchemaError("Wrong value type '%s' for field '%s'" % (value, self._field))
    def __iter__(self):
        """ iterator over values """
        for x in self.value: yield x
            
    def __getitem__(self, idx):
        return self.value[idx]

    def __setitem__(self, idx, value):
        # TODO validate !!!
        raise Warning("TODO implement validate")
        self.value[idx] = value  
        
class VectorField(DocField):
    """
        usage: 
            doc.terms # vector
            doc.terms['chat'] # vectoritem
            doc.terms['chat'].tf = 12
            
    """
    def __init__(self, fieldtype):
        DocField.__init__(self, fieldtype)
        self._attrs =  {} # attr_name : [FieldType, ]
        self._keys = {}   # key: idx
    
    def attribute_names(self):
        return self._attrs.keys()
        
    def clear_attributes(self):
        self._attrs =  {} # removes all attr
        for name, attr_field in self._field.attrs.iteritems():
            self._attrs[name] = []
       
    def __repr__(self):
        return "<%s:%s >" %( self.__class__.__name__, self._attrs.keys() )
    
    def __str__(self) : return self.__repr__()
    
    def __len__(self):
        """ Vector keys count """
        return len(self._keys)
        
    def __iter__(self):
        return self._keys.iterkeys()
        
    def keys(self): 
        """ list of keys in the vector """
        return self._keys.keys()

    def __contains__(self, key):
        """ 
            Return True if the vector has the specified key 
            vector.has('mykey')
            >>> False 
        """
        return key in self._keys
        
    def has(self, key): 
        return self.__contains__(key)

    def __getitem__(self, key):
        return VectorItem(self, key )
    
    def get_value(self): 
        """ from DocField, convenient method """
        return self

    def add(self, key):
        """ Add a key to the vector """
        if not self.has(key):
            self._keys[key] = len(self._keys)
        #append to attributes
        for name, attr_field  in self._field.attrs.iteritems():
            self._attrs[name].append(create_field(attr_field))
        
    def set(self, keys):
        """ set new keys 
            Mind this will clear all attributes and keys before adding new keys
            doc.terms = ['a', 'b']
        """
        # clear keys and atributes
        self._keys = {}
        _field = self._field 
        self.clear_attributes()
        for key in keys:
            if not self.has(key):
                self.add(_field.validate(key))
                
    def get_attr_value(self, key , attr):
        idx = self._keys[key]
        return self._attrs[attr][idx].get_value()
    
    def set_attr_value(self, key, attr, value):
        idx = self._keys[key]
        self._attrs[attr][idx].set(value)

    def __getattr__(self, name):
        """
            :param name: attribute name
        """
        if name in self._attrs: 
            return VectorAttr(self, name)
        else :
            raise SchemaError("No such attribute '%s' in Vector" % name)
    
    def __setattr__(self, name, values):
        """
            doc.terms.x = [1,2]
        """
        if name.startswith('_'):
            DocField.__setattr__(self, name, values)
            #self.__dict__[attr] = value
        elif self.__dict__['_attrs'].has_key(name):
            if len(values) != len(self):
                raise SchemaError('Wrong size : |values| (%s) should be equals to |keys| (%s) '\
                        %(len(values), len(self)))
            _attr = [ create_field(self._field.attrs[name]) for x in xrange(len(values)) ]
            for i, v in enumerate(values) :
                _attr[i].set(v)
            self._attrs[name] = _attr

class VectorAttr(object):
    def __init__(self, vector, attr):
        self.vector = vector
        self.attr = attr
            
    def __iter__(self):
        for attr_value in self.vector._attrs[self.attr]:
            yield attr_value.get_value()
    
    def values(self):
        # should we use doc.terms.tf() ??? 
        return list(self)
            
    def __getslice__(self, i, j):
        return self.vector._attrs[self.attr][i:j]
    
    def __getitem__(self, idx):
        return self.vector._attrs[self.attr][idx]
        
    def __setitem__(self, idx, value):
        self.vector._attrs[self.attr][idx] = value
        
    
    
    
class VectorItem(object):
    def __init__(self, vector, key):
        self._vector = vector
        self._key = key
    
    def attribute_names(self):
        return self._vector.attribute_names()
    
    def as_dict(self):
        return { k: self[k] for k in self.attribute_names()  }
        
    def __getattr__(self, attr_name):
        if attr_name.startswith('_'):
            return self.__getattribute__(attr_name) # XXXX WTF ???
        return self._vector.get_attr_value(self._key, attr_name)
    
    def __setattr__(self, attr, value):
        if not(attr.startswith('_')):
            self._vector.set_attr_value(self._key, attr, value)
        else: 
            object.__setattr__(self, attr, value)
            
    def __getitem__(self, name ):
        return getattr(self, name)


def create_field(field):
    """
    Create a convenient field to store data
    """
    if not(field.multi):
         return ValueField(field)
    elif field.multi and not field.uniq:
        return ListField(field)
    elif field.multi and field.uniq and field.attrs == None:
        return SetField(field)    
    else:
        return VectorField(field)

class Doc(dict):
    
    __reserved__ = ['docnum', 'schema']
        
    
    def __init__(self, schema, **data):
        # schema 
        self['schema'] = schema
        # fields value(s)
        
        # Doc should always have a docnum ?
        self['docnum'] = data['docnum'] # or fail
        
        for key,field in schema.iter_fields():
            # field.multi & ! field.uniq >> list
            # field.multi & field.uniq >> set
            # field.multi & field.uniq & fields.attr >> dict
            # ! field.multi >> default or None
            self[key] = create_field(field) 
            if data and data.has_key(key):
                self[key].set(data[key])
            
    def __getattr__(self, name):
        try:
            if name == 'schema':
                return self['schema']
            return self[name].get_value()
        
        except KeyError as e:
            raise AttributeError("%s is not a Doc field (existing attributes are: %s)" % (e, self.keys()))

    def __setattr__(self, name, value):
        assert name in self['schema'].field_names(), \
            "%s is not declared as a field in the schema" %name
        self[name].set( value )
        