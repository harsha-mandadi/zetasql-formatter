#
# Copyright 2019 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

"""Defines parse tree nodes for the ZetaSQL parser.

This program defines parse tree node subclasses of ASTNode. It generates
headers, protos and other files from templates.

Still a work in progress.

"""

import collections.abc
import enum
import operator
import re

from absl import app
from absl import flags
import jinja2

from zetasql.parser import ast_enums_pb2
from zetasql.parser.generator_utils import CleanIndent
from zetasql.parser.generator_utils import JavaDoc
from zetasql.parser.generator_utils import LowerCamelCase
from zetasql.parser.generator_utils import NameToNodeKindName
from zetasql.parser.generator_utils import ScalarType
from zetasql.parser.generator_utils import Trim
from zetasql.parser.generator_utils import UpperCamelCase

ROOT_NODE_NAME = 'ASTNode'

_make_enum_name_re = re.compile(r'([a-z])([A-Z])')


def NormalCamel(name):
  """Convert C++ ASTClassName into normalized AstClassName.

  A few legacy classes have irregular names requiring special-casing in order to
  be remapped to an ASTNodeKind.

  Args:
    name: name of the C++ class.
  Returns:
    Normalized camel-case equivalent of the class name.
  """
  if name == 'ASTBigNumericLiteral':
    return 'AstBignumericLiteral'
  elif name == 'ASTJSONLiteral':
    return 'AstJsonLiteral'
  elif name == 'ASTTVFSchema':
    return 'AstTvfSchema'
  elif name == 'ASTTVF':
    return 'AstTvf'
  elif name == 'ASTTVFArgument':
    return 'AstTvfArgument'
  elif name == 'ASTTVFSchemaColumn':
    return 'AstTvfSchemaColumn'
  else:
    return name.replace('AST', 'Ast')


def GetNodeKindOneOfValue(name):
  """Convert a camel-case c++ ClassName to corresponding oneof proto enum.

  Used to construct case constants for deserializing AnyASTxxx message for
  abstract classes into the correct final class.

  Args:
    name: name of the C++ class.

  Returns:
    String constant formatted as the enum used in case statement.

  """
  return 'k' + NormalCamel(name) + 'Node'


def NameToNodeKind(name):
  """Convert camel-case C++ ASTClassName to AST_CLASS_NAME in ASTNodeKind."""
  return _make_enum_name_re.sub(r'\1_\2', NormalCamel(name)).upper()

SCALAR_BOOL = ScalarType(
    'bool',
    java_type='boolean',
    cpp_default='false')

SCALAR_BOOL_DEFAULT_TRUE = ScalarType(
    'bool',
    java_type='boolean',
    cpp_default='true')

SCALAR_STRING = ScalarType(
    'std::string',
    java_type='String',
    proto_type='string')

SCALAR_ID_STRING = ScalarType(
    'IdString',
    java_type='String',
    proto_type='string')

SCALAR_INT = ScalarType(
    'int',
    proto_type='int64',
    java_type='long',
    cpp_default='0')

# enum in type.proto
SCALAR_TYPE_KIND = ScalarType(
    'TypeKind',
    proto_type='zetasql.TypeKind',
    cpp_default='TYPE_UNKNOWN')


def EnumScalarType(enum_name, node_name, cpp_default):
  """Create a ScalarType for enums defined in ast_enums.proto.

  Args:
    enum_name: name of the enum.
    node_name: name of the ASTNode that this enum belongs to, or empty if this
               enum is not class specific.
    cpp_default: default value for c++.
  Returns:
    The ScalarType.
  """
  return ScalarType(
      ctype=enum_name,
      proto_type='%sEnums.%s' % (node_name, enum_name),
      is_enum=True,
      scoped_ctype='%s::%s' % (node_name, enum_name),
      cpp_default=cpp_default)

SCALAR_SCHEMA_OBJECT_KIND = EnumScalarType('SchemaObjectKind', '',
                                           'kInvalidSchemaObjectKind')

SCALAR_BINARY_OP = EnumScalarType('Op', 'ASTBinaryExpression', 'NOT_SET')

SCALAR_ORDERING_SPEC = EnumScalarType('OrderingSpec', 'ASTOrderingExpression',
                                      'UNSPECIFIED')

SCALAR_JOIN_TYPE = EnumScalarType('JoinType', 'ASTJoin', 'DEFAULT_JOIN_TYPE')

SCALAR_JOIN_HINT = EnumScalarType('JoinHint', 'ASTJoin', 'NO_JOIN_HINT')

SCALAR_AS_MODE = EnumScalarType('AsMode', 'ASTSelectAs', 'NOT_SET')

SCALAR_NULL_HANDLING_MODIFIER = EnumScalarType('NullHandlingModifier',
                                               'ASTFunctionCall',
                                               'DEFAULT_NULL_HANDLING')

SCALAR_MODIFIER = EnumScalarType('Modifier', 'ASTExpressionSubquery', 'NONE')

SCALAR_MODIFIER_KIND = EnumScalarType('ModifierKind', 'ASTHavingModifier',
                                      'MAX')
SCALAR_OPERATION_TYPE = EnumScalarType('OperationType', 'ASTSetOperation',
                                       'NOT_SET')

SCALAR_OPERATION_TYPE = EnumScalarType('OperationType', 'ASTSetOperation',
                                       'NOT_SET')

SCALAR_UNARY_OP = EnumScalarType('Op', 'ASTUnaryExpression', 'NOT_SET')

SCALAR_FRAME_UNIT = EnumScalarType('FrameUnit', 'ASTWindowFrame', 'RANGE')

SCALAR_BOUNDARY_TYPE = EnumScalarType('BoundaryType', 'ASTWindowFrameExpr',
                                      'UNBOUNDED_PRECEDING')

SCALAR_ANY_SOME_ALL_OP = EnumScalarType('Op', 'ASTAnySomeAllOp',
                                        'kUninitialized')
SCALAR_READ_WRITE_MODE = EnumScalarType('Mode', 'ASTTransactionReadWriteMode',
                                        'INVALID')

SCALAR_IMPORT_KIND = EnumScalarType('ImportKind', 'ASTImportStatement',
                                    'MODULE')

SCALAR_NULL_FILTER = EnumScalarType('NullFilter', 'ASTUnpivotClause',
                                    'kUnspecified')

SCALAR_SCOPE = EnumScalarType('Scope', 'ASTCreateStatement', 'DEFAULT_SCOPE')

SCALAR_SQL_SECURITY = EnumScalarType('SqlSecurity', 'ASTCreateStatement',
                                     'SQL_SECURITY_UNSPECIFIED')

SCALAR_PROCEDURE_PARAMETER_MODE = EnumScalarType('ProcedureParameterMode',
                                                 'ASTFunctionParameter',
                                                 'NOT_SET')

SCALAR_TEMPLATED_TYPE_KIND = EnumScalarType('TemplatedTypeKind',
                                            'ASTTemplatedParameterType',
                                            'UNINITIALIZED')

SCALAR_STORED_MODE = EnumScalarType('StoredMode', 'ASTGeneratedColumnInfo',
                                    'NON_STORED')

SCALAR_RELATIVE_POSITION_TYPE = EnumScalarType('RelativePositionType',
                                               'ASTColumnPosition', 'PRECEDING')

SCALAR_INSERT_MODE = EnumScalarType('InsertMode', 'ASTInsertStatement',
                                    'DEFAULT_MODE')

SCALAR_PARSE_PROGRESS = EnumScalarType('ParseProgress', 'ASTInsertStatement',
                                       'kInitial')

SCALAR_ACTION_TYPE = EnumScalarType('ActionType', 'ASTMergeAction', 'NOT_SET')

SCALAR_MATCH_TYPE = EnumScalarType('MatchType', 'ASTMergeWhenClause', 'NOT_SET')

SCALAR_FILTER_TYPE = EnumScalarType('FilterType', 'ASTFilterFieldsArg',
                                    'NOT_SET')

SCALAR_UNIT = EnumScalarType('Unit', 'ASTSampleSize',
                             'NOT_SET')

SCALAR_ACTION = EnumScalarType('Action', 'ASTForeignKeyActions', 'NO_ACTION')

SCALAR_MATCH = EnumScalarType('Match', 'ASTForeignKeyReference', 'SIMPLE')

SCALAR_BREAK_CONTINUE_KEYWORD_DEFAULT_BREAK = EnumScalarType(
    'BreakContinueKeyword', 'ASTBreakContinueStatement', 'BREAK')

SCALAR_BREAK_CONTINUE_KEYWORD_DEFAULT_CONTINUE = EnumScalarType(
    'BreakContinueKeyword', 'ASTBreakContinueStatement', 'CONTINUE')

SCALAR_DROP_MODE = EnumScalarType('DropMode', 'ASTDropStatement',
                                  'DROP_MODE_UNSPECIFIED')

SCALAR_DETERMINISM_LEVEL = EnumScalarType('DeterminismLevel',
                                          'ASTCreateFunctionStmtBase',
                                          'DETERMINISM_UNSPECIFIED')

SCALAR_LOAD_INSERTION_MODE = EnumScalarType(
    'InsertionMode', 'ASTAuxLoadDataStatement', 'NOT_SET')


# Identifies the FieldLoader method used to populate member fields.
# Each node field in a subclass is added to the children_ vector in ASTNode,
# then additionally added to a type-specific field in the subclass using one
# of these methods:
# REQUIRED: The next node in the vector, which must exist, is used for this
#           field.
# OPTIONAL: The next node in the vector, if it exists, is used for this field.
# OPTIONAL_EXPRESSION: The next node in the vector for which IsExpression()
#           is true, if it exists, is used for this field.
# OPTIONAL_TYPE: The next node in the vector for which IsType()
#           is true, if it exists, is used for this field.
# REST_AS_REPEATED: All remaining nodes, if any, are used for this field,
#           which should be a vector type.
# REPEATING_WHILE_IS_NODE_KIND: Appends remaining nodes to the vector, stopping
#           when the node kind of next node is not 'node_kind'.
# REPEATING_WHILE_IS_EXPRESSION: Appends remaining nodes to the vector, stopping
#           when the next node is !IsExpression().
# See Add* methods in ast_node.h for further details.
class FieldLoaderMethod(enum.Enum):
  REQUIRED = 0
  OPTIONAL = 1
  REST_AS_REPEATED = 2
  OPTIONAL_EXPRESSION = 3
  OPTIONAL_TYPE = 4
  REPEATING_WHILE_IS_NODE_KIND = 5
  REPEATING_WHILE_IS_EXPRESSION = 6


# Specifies visibility of a Field.
class Visibility(enum.Enum):
  PRIVATE = 0
  PROTECTED = 1


def Field(name,
          ctype,
          tag_id,
          field_loader=FieldLoaderMethod.OPTIONAL,
          comment=None,
          private_comment=None,
          gen_setters_and_getters=True,
          getter_is_override=False,
          visibility=Visibility.PRIVATE):
  """Make a field to put in a node class.

  Args:
    name: field name
    ctype: c++ type for this field
           Should be a ScalarType like an int, string or enum type,
           or the name of a node class type (e.g. ASTExpression).
           Cannot be a pointer type, and should not include modifiers like
           const.
    tag_id: Unique sequential id for this field within the node, beginning with
            2, which should not change.
    field_loader: FieldLoaderMethod enum specifies which FieldLoader method
           to use for this field. Ignored when Node has gen_init_fields=False.
           Not applicable to scalar types.
    comment: Comment for this field's public getter/setter method. Text will be
             stripped and de-indented.
    private_comment: Comment for the field in the protected/private section.
    gen_setters_and_getters: When False, suppress generation of default
           template-based get and set methods. Non-standard alternatives
           may be supplied in extra_public_defs.
    getter_is_override: Indicates getter overrides virtual method in superclass.
    visibility: Indicates whether field is private or protected.
  Returns:
    The newly created field.

  Raises:
    RuntimeError: If an error is detected in one or more arguments.
  """
  if field_loader in (FieldLoaderMethod.REST_AS_REPEATED,
                      FieldLoaderMethod.REPEATING_WHILE_IS_NODE_KIND,
                      FieldLoaderMethod.REPEATING_WHILE_IS_EXPRESSION):
    is_vector = True
    proto_optional_or_repeated = 'repeated'
  else:
    is_vector = False
    proto_optional_or_repeated = 'optional'
  if not gen_setters_and_getters:
    assert comment is None, ('Accessor comments cannot be used when'
                             ' gen_setters_and_getters is False')
  assert tag_id >= 2, ('Error, tag_id must be >=2 for field %s' % name)
  member_name = name + '_'
  getter_override = ''
  if getter_is_override:
    assert gen_setters_and_getters, ('getter_is_override cannot be used when '
                                     'gen_setters_and_getters is false')
    getter_override = 'override '
  if isinstance(ctype, ScalarType):
    assert field_loader == FieldLoaderMethod.OPTIONAL, ('field_loader should '
                                                        'not be specified for '
                                                        'scalar field %s' %
                                                        name)
    member_type = ctype.ctype
    cpp_default = ctype.cpp_default
    is_node_ptr = False
    node_kind = None
    element_storage_type = None
    proto_type = ctype.proto_type
    if ctype.is_enum:
      is_enum = True
      enum_value = proto_type.replace('.', '_')
      if proto_type == 'Enums.SchemaObjectKind':
        proto_type = 'SchemaObjectKind'
        enum_value = 'SchemaObjectKind'
        java_type = 'SchemaObjectKind'
      else:
        java_type = ctype.proto_type
    else:
      is_enum = False
      enum_value = None
      java_type = ctype.java_type
    full_java_type = java_type
  else:
    is_enum = False
    enum_value = None
    element_storage_type = 'const %s*' % ctype
    node_kind = NameToNodeKind(ctype)
    proto_type = proto_type = '%sProto' % ctype  # _ComputeHierarchy may update
    if is_vector:
      member_type = 'absl::Span<%s const>' % element_storage_type
      cpp_default = ''
      is_node_ptr = False
      java_type = ctype
      full_java_type = 'ImmutableList<%s>' % java_type
    else:
      member_type = 'const %s*' % ctype
      cpp_default = 'nullptr'
      is_node_ptr = True
      java_type = ctype
      full_java_type = java_type
  return {
      'ctype': ctype,
      'java_type': java_type,
      'full_java_type': full_java_type,
      'cpp_default': cpp_default,
      'member_name': member_name,  # member variable name
      'name': name,  # name without trailing underscore
      'comment': CleanIndent(comment, prefix='  // '),
      'private_comment': CleanIndent(private_comment, prefix='  // '),
      'private_javadoc': JavaDoc(private_comment, indent=4),
      'javadoc': JavaDoc(comment, indent=4),
      'member_type': member_type,
      'is_node_ptr': is_node_ptr,
      'field_loader': field_loader.name,
      'node_kind': node_kind,
      'is_vector': is_vector,
      'element_storage_type': element_storage_type,
      'gen_setters_and_getters': gen_setters_and_getters,
      'getter_override': getter_override,
      'visibility': visibility.name,
      'tag_id': tag_id,
      'proto_type': proto_type,
      'proto_optional_or_repeated': proto_optional_or_repeated,
      'is_enum': is_enum,
      'enum_value': enum_value,
  }

# Ancestor holds the subset of a NodeDict needed to serialize its
# immediate ancestor.
Ancestor = collections.namedtuple('Ancestor', [
    'tag_id', 'parent_name', 'proto_field_type', 'member_name',
    'container_type'
])

# InitField holds the attributes of a field needed to add it in InitFields().
InitField = collections.namedtuple('InitField', [
    'field_loader', 'member_name', 'node_kind'])


class TreeGenerator(object):
  """Generates code to define tree objects.
  """

  def __init__(self):
    self.nodes = []
    self.node_map = {}  #  {node_name : NodeDict}
    self.root_child_nodes = {}  #  {tag_id : NodeDict}

  def AddNode(self,
              name,
              tag_id,
              parent,
              is_abstract=False,
              fields=None,
              extra_public_defs='',
              extra_protected_defs='',
              extra_private_defs='',
              comment=None,
              use_custom_debug_string=False,
              custom_debug_string_comment=None,
              init_fields_order=None,
              gen_init_fields=None):
    """Add a node class to be generated.

    Args:
      name: class name for this node
      tag_id: unique sequential id for this node, which should not change.
          Next tag_id: 337
      parent: class name of the parent node
      is_abstract: true if this node is an abstract class
      fields: list of fields in this class; created with Field function
      extra_public_defs: extra public C++ definitions to add to the public
          portion of the header.
      extra_protected_defs: extra C++ definitions to add to the protected
          portion of the header.
      extra_private_defs: extra C++ definitions to add to the private
          portion of the header. Overrides to InitFields() should be here.
      comment: Class level comment text for this node. Text will be stripped and
          de-indented.
      use_custom_debug_string: If True, generate prototype for overridden
          SingleNodeDebugString method.
      custom_debug_string_comment: Optional comment for SingleNodeDebugString
          method.
      init_fields_order: Optional override to the default ordering of field
          initialization, which must match the grammar as defined in
          bison_parser.y. The generated method by default initializes all node
          fields, including inherited fields, in order of declaration, starting
          with the final class. To use a different order, specify a list
          of field names here. Inherited fields which are marked optional may
          be omitted if they are not used in the final class.
      gen_init_fields: May be set to False in final classes to suppress
          generation of a default InitFields() method, in which case a custom
          InitFields() must be provide in extra_private_defs. Not applicable
          to non-final classes.
    """
    enum_defs = self._GenEnums(name)
    proto_type = '%sProto' % name

    if fields is None:
      fields = []
    if is_abstract:
      class_final = ''
      proto_field_type = 'Any%sProto' % name
      assert gen_init_fields is None, ('gen_init_fields cannot be used for '
                                       'non-final class {}').format(name)
    else:
      class_final = 'final '
      proto_field_type = proto_type
      if gen_init_fields is None:
        gen_init_fields = True
      elif not gen_init_fields:
        assert ('absl::Status InitFields() final {' in extra_private_defs), (
            'class {} must provide InitFields() in extra_private_defs when '
            'gen_init_fields=False').format(name)
    node_kind = NameToNodeKind(name)

    visibility_types = ['public:', 'protected:', 'private:']
    assert (type not in extra_public_defs for type in visibility_types
           ), 'visibility specifiers should not be used in extra_public_defs'
    assert (type not in extra_protected_defs for type in visibility_types
           ), 'visibility specifiers should not be used in extra_protected_defs'
    assert (type not in extra_private_defs for type in visibility_types
           ), 'visibility specifiers should not be used in extra_private_defs'

    has_private_fields = False
    has_protected_fields = False
    for field in fields:
      if field['visibility'] == 'PRIVATE':
        has_private_fields = True
      elif field['visibility'] == 'PROTECTED':
        has_protected_fields = True
    assert not (
        (has_protected_fields or extra_protected_defs) and not is_abstract), (
            'protected fields and methods cannot be used in final class %s',
            name)

    if custom_debug_string_comment:
      assert use_custom_debug_string, ('custom_debug_string_comment should be '
                                       'used with use_custom_debug_string')
      custom_debug_string_comment = CleanIndent(
          custom_debug_string_comment, prefix='// ')

    # This dict is referred to as a NodeDict elsewhere in the comments.
    node_dict = {
        'name': name,
        'parent': parent,
        'class_final': class_final,
        'is_abstract': is_abstract,
        'comment': CleanIndent(comment, prefix='// '),
        'fields': fields,
        'node_kind': node_kind,
        'extra_public_defs': extra_public_defs.rstrip(),
        'extra_protected_defs': extra_protected_defs.lstrip('\n').rstrip(),
        'extra_private_defs': extra_private_defs.lstrip('\n').rstrip(),
        'use_custom_debug_string': use_custom_debug_string,
        'custom_debug_string_comment': custom_debug_string_comment,
        'gen_init_fields': gen_init_fields,
        'has_private_fields': has_private_fields,
        'has_protected_fields': has_protected_fields,
        'enum_defs': enum_defs,
        'proto_field_type': proto_field_type,
        'proto_type': proto_type,
        'parent_proto_type': '%sProto' % parent,
        'tag_id': tag_id,
        'member_name': NameToNodeKind(name).lower(),
        'node_kind_name': NameToNodeKindName(name, 'AST'),
        'subclasses': {},  # {tag_id : NodeDict}
        'node_kind_oneof_value': GetNodeKindOneOfValue(name),
        'init_fields_order': init_fields_order,
        'javadoc': JavaDoc(comment, 2),
    }

    self.nodes.append(node_dict)
    assert name not in self.node_map, ('error, duplicate node name %s' % name)
    self.node_map[name] = node_dict

  def _GenEnums(self, cpp_class_name):
    """Gen C++ enums from the corresponding <cpp_class_name>Enums proto message.

    Args:
      cpp_class_name: C++ class name the enums should be imported into.

    Returns:
      A list of lines, one per enum, for inclusion in the C++ header file.
    """
    message_types = ast_enums_pb2.DESCRIPTOR.message_types_by_name
    message_name = cpp_class_name + 'Enums'
    if message_name not in message_types:
      return []

    enum_defs = []
    for enum_type in message_types[message_name].enum_types:
      enum_values = []
      comment = '// This enum is equivalent to %s::%s in ast_enums.proto\n' % (
          message_name, enum_type.name)
      for value in enum_type.values:
        enum_val = '\n    %s = %s::%s' % (value.name, message_name, value.name)
        enum_values.append(enum_val)
      enum_def = '%s  enum %s { %s \n  };' % (comment, enum_type.name,
                                              ', '.join(enum_values))
      enum_defs.append(enum_def)
    return enum_defs

  def _GetNodeByName(self, name):
    return self.node_map[name]

  def _ComputeHierarchy(self):
    """Determine class hierarchy.

    This method does 3 things:
    - Sets the correct proto_type for each node-type field in each node
    - populates the subclasses dict for each abstract class with a mapping of
      tag_id->subclass NodeDict for each of its immediate subclasses
    - recursively populates a dict of tag_id->ancestor for each ancestor of each
      class.
    """
    assert not self.root_child_nodes

    def TraverseToRoot(node, ancestors, init_fields):
      """Recursively ascend node's parents to build list of parents' subclasses.

      Also builds a list of all the node's fields which need to be included
      in InitFields().

      End recursion when root node is reached.
      Args:
        node: Node to search up from.
        ancestors: a dict built via recursion of tag_id->Ancester.
        init_fields: A list of InitFields.
      """
      # The list of init_fields is built from the lowest class first, adding
      # fields according to order of declaration, then doing the same at
      # each level up.
      for field in node['fields']:
        if field['is_node_ptr'] or field['is_vector']:
          init_field = InitField(field['field_loader'], field['member_name'],
                                 field['node_kind'])
          init_fields.append(init_field)
      parent_name = node['parent']
      if parent_name != ROOT_NODE_NAME:
        parent_node = self._GetNodeByName(parent_name)
        ancestor = Ancestor(parent_node['tag_id'], parent_name,
                            parent_node['proto_field_type'],
                            node['member_name'], node['proto_field_type'])
        ancestors[ancestor.tag_id] = ancestor
        TraverseToRoot(parent_node, ancestors, init_fields)
        parent_subclasses = parent_node['subclasses']
      else:
        parent_subclasses = self.root_child_nodes

      parent_subclasses[node['tag_id']] = node

    for node in self.nodes:
      # If a field is node type ASTFoo, its proto_type will be either
      # ASTFooProto if ASTFoo is final or AnyASTFooProto if abstract.
      # Get from node's proto_field_type.
      for field in node['fields']:
        ctype = field['ctype']
        if ctype in self.node_map:
          field_node = self._GetNodeByName(ctype)
          field['proto_type'] = field_node['proto_field_type']
      ancestors = {}  #  {tag_id : Ancestor}
      init_fields = []
      TraverseToRoot(node, ancestors, init_fields)
      node['ancestors'] = ancestors
      if node['init_fields_order']:
        init_fields_order_members = [
            field + '_' for field in node['init_fields_order']
        ]
        init_fields_dict = {field.member_name: field for field in init_fields}
        assert set(init_fields_order_members).issubset(init_fields_dict), (
            'in class {} init_fields_order {} contains invalid field names not '
            'present in {}').format(node['name'], node['init_fields_order'],
                                    list(init_fields_dict.keys()))
        init_fields = []
        for field_name in init_fields_order_members:
          init_fields.append(init_fields_dict[field_name])
      node['init_fields'] = init_fields

  def Generate(
      self,
      output_path,
      template_path=None):
    """Materialize the template to generate the output file."""

    jinja_env = jinja2.Environment(
        undefined=jinja2.StrictUndefined,
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
        line_statement_prefix='# ',
        loader=jinja2.FileSystemLoader('', followlinks=True))

    # {{items|sort_by_tag_id}} can be used to sort a list of objects by tag.
    def SortByTagId(items):
      return sorted(items, key=operator.itemgetter('tag_id'))

    jinja_env.filters['sort_by_tag_id'] = SortByTagId
    jinja_env.filters['lower_camel_case'] = LowerCamelCase
    jinja_env.filters['upper_camel_case'] = UpperCamelCase
    self._ComputeHierarchy()

    context = {
        'nodes': self.nodes,
        'root_child_nodes': self.root_child_nodes,
        # For when we need to force a blank line and jinja wants to
        # eat blank lines from the template.
        'blank_line': '\n'
    }

    template = jinja_env.get_template(template_path)
    out = open(output_path, 'wt')
    out.write(Trim(template.render(context)))
    out.close()


def main(argv):
  if len(argv) != 3:
    raise Exception(
        'Usage: %s <output/path/to/parse_tree_generated.h> <input/path/to/parse_tree_generated.h.template>'
    )

  output_path = argv[1]
  template_path = argv[2]

  gen = TreeGenerator()

  gen.AddNode(
      name='ASTStatement',
      tag_id=1,
      parent='ASTNode',
      is_abstract=True,
      comment="""
    Superclass of all Statements.
      """,
      extra_public_defs="""
  bool IsStatement() const final { return true; }
  bool IsSqlStatement() const override { return true; }
      """
    )

  gen.AddNode(
      name='ASTQueryStatement',
      tag_id=2,
      parent='ASTStatement',
      comment="""
    Represents a single query statement.
      """,
      fields=[
          Field(
              'query',
              'ASTQuery',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
      ])

  gen.AddNode(
      name='ASTQueryExpression',
      tag_id=3,
      parent='ASTNode',
      is_abstract=True,
      comment="""
    Superclass for all query expressions.  These are top-level syntactic
    constructs (outside individual SELECTs) making up a query.  These include
    Query itself, Select, UnionAll, etc.
      """,
      extra_public_defs="""
  bool IsQueryExpression() const override { return true; }
      """,
      fields=[
          Field(
              'parenthesized',
              SCALAR_BOOL,
              tag_id=2)
      ])

  gen.AddNode(
      name='ASTQuery',
      tag_id=4,
      parent='ASTQueryExpression',
      fields=[
          Field(
              'with_clause',
              'ASTWithClause',
              tag_id=2,
              comment="""
      If present, the WITH clause wrapping this query.
            """),
          Field(
              'query_expr',
              'ASTQueryExpression',
              tag_id=3,
              field_loader=FieldLoaderMethod.REQUIRED,
              comment="""
      The query_expr can be a single Select, or a more complex structure
      composed out of nodes like SetOperation and Query.
            """),
          Field(
              'order_by',
              'ASTOrderBy',
              tag_id=4,
              comment="""
      If present, applies to the result of <query_expr_> as appropriate.
            """),
          Field(
              'limit_offset',
              'ASTLimitOffset',
              tag_id=5,
              comment="""
      If present, this applies after the result of <query_expr_> and
      <order_by_>.
            """),
          Field('is_nested', SCALAR_BOOL, tag_id=6),
          Field(
              'is_pivot_input',
              SCALAR_BOOL,
              tag_id=7,
              comment="""
                True if this query represents the input to a pivot clause.
                """)
      ],
      use_custom_debug_string=True
      )

  gen.AddNode(
      name='ASTSelect',
      tag_id=5,
      parent='ASTQueryExpression',
      use_custom_debug_string=True,
      fields=[
          Field(
              'hint',
              'ASTHint',
              tag_id=2),
          Field(
              'anonymization_options',
              'ASTOptionsList',
              tag_id=3),
          Field(
              'distinct',
              SCALAR_BOOL,
              tag_id=4),
          Field(
              'select_as',
              'ASTSelectAs',
              tag_id=5),
          Field(
              'select_list',
              'ASTSelectList',
              tag_id=6,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'from_clause',
              'ASTFromClause',
              tag_id=7),
          Field(
              'where_clause',
              'ASTWhereClause',
              tag_id=8),
          Field(
              'group_by',
              'ASTGroupBy',
              tag_id=9),
          Field(
              'having',
              'ASTHaving',
              tag_id=10),
          Field(
              'qualify',
              'ASTQualify',
              tag_id=11),
          Field(
              'window_clause',
              'ASTWindowClause',
              tag_id=12),
      ])

  gen.AddNode(
      name='ASTSelectList',
      tag_id=6,
      parent='ASTNode',
      fields=[
          Field(
              'columns',
              'ASTSelectColumn',
              tag_id=2,
              field_loader=FieldLoaderMethod.REST_AS_REPEATED),
      ])

  gen.AddNode(
      name='ASTSelectColumn',
      tag_id=7,
      parent='ASTNode',
      fields=[
          Field(
              'expression',
              'ASTExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'alias',
              'ASTAlias',
              tag_id=3)
      ])

  gen.AddNode(
      name='ASTExpression',
      tag_id=8,
      parent='ASTNode',
      is_abstract=True,
      extra_public_defs="""
  bool IsExpression() const override { return true; }

  // Returns true if this expression is allowed to occur as a child of a
  // comparison expression. This is not allowed for unparenthesized comparison
  // expressions and operators with a lower precedence level (AND, OR, and NOT).
  virtual bool IsAllowedInComparison() const { return true; }
      """,
      fields=[
          Field(
              'parenthesized',
              SCALAR_BOOL,
              tag_id=2)
      ])

  gen.AddNode(
      name='ASTLeaf',
      tag_id=9,
      parent='ASTExpression',
      is_abstract=True,
      use_custom_debug_string=True,
      extra_public_defs="""
  // image() references data with the same lifetime as this ASTLeaf object.
  absl::string_view image() const { return image_; }
  void set_image(std::string image) { image_ = std::move(image); }

  bool IsLeaf() const override { return true; }
      """,
      fields=[
          Field(
              'image',
              SCALAR_STRING,
              tag_id=2,
              gen_setters_and_getters=False)
      ])

  gen.AddNode(
      name='ASTIntLiteral',
      tag_id=10,
      parent='ASTLeaf',
      extra_public_defs="""

  bool is_hex() const;
      """,
      )

  gen.AddNode(
      name='ASTIdentifier',
      tag_id=11,
      parent='ASTExpression',
      use_custom_debug_string=True,
      extra_public_defs="""
  // Set the identifier string.  Input <identifier> is the unquoted identifier.
  // There is no validity checking here.  This assumes the identifier was
  // validated and unquoted in zetasql.jjt.
  void SetIdentifier(IdString identifier) {
    id_string_ = identifier;
  }

  // Get the unquoted and unescaped string value of this identifier.
  IdString GetAsIdString() const { return id_string_; }
  std::string GetAsString() const { return id_string_.ToString(); }
  absl::string_view GetAsStringView() const {
    return id_string_.ToStringView();
  }
      """,
      fields=[
          Field(
              'id_string',
              SCALAR_ID_STRING,
              tag_id=2,
              gen_setters_and_getters=False)
      ])

  gen.AddNode(
      name='ASTAlias',
      tag_id=12,
      parent='ASTNode',
      fields=[
          Field(
              'identifier',
              'ASTIdentifier',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
      ],
      extra_public_defs="""
  // Get the unquoted and unescaped string value of this alias.
  std::string GetAsString() const;
  absl::string_view GetAsStringView() const;
  IdString GetAsIdString() const;
      """
    )

  gen.AddNode(
      name='ASTGeneralizedPathExpression',
      tag_id=13,
      parent='ASTExpression',
      is_abstract=True,
      comment="""
 Parent class that corresponds to the subset of ASTExpression nodes that are
 allowed by the <generalized_path_expression> grammar rule. It allows for some
 extra type safety vs. simply passing around ASTExpression as
 <generalized_path_expression>s.

 Only the following node kinds are allowed:
 - AST_PATH_EXPRESSION
 - AST_DOT_GENERALIZED_FIELD where the left hand side is a
   <generalized_path_expression>.
 - AST_DOT_IDENTIFIER where the left hand side is a
   <generalized_path_expression>.
 - AST_ARRAY_ELEMENT where the left hand side is a
   <generalized_path_expression>

 Note that the type system does not capture the "pureness constraint" that,
 e.g., the left hand side of an AST_DOT_GENERALIZED_FIELD must be a
 <generalized_path_expression> in order for the node. However, it is still
 considered a bug to create a variable with type ASTGeneralizedPathExpression
 that does not satisfy the pureness constraint (similarly, it is considered a
 bug to call a function with an ASTGeneralizedPathExpression argument that
 does not satisfy the pureness constraint).
    """,
      extra_public_defs="""
  // Returns an error if 'path' contains a node that cannot come from the
  // <generalized_path_expression> grammar rule.
  static absl::Status VerifyIsPureGeneralizedPathExpression(
      const ASTExpression* path);
      """)

  gen.AddNode(
      name='ASTPathExpression',
      tag_id=14,
      parent='ASTGeneralizedPathExpression',
      comment="""
 This is used for dotted identifier paths only, not dotting into
 arbitrary expressions (see ASTDotIdentifier below).
      """,
      fields=[
          Field(
              'names',
              'ASTIdentifier',
              tag_id=2,
              field_loader=FieldLoaderMethod.REST_AS_REPEATED,
              gen_setters_and_getters=False),
      ],
      # The existing API unfortunately uses name(int i) rather than names(int i)
      extra_public_defs="""
  const int num_names() const { return names_.size(); }
  const absl::Span<const ASTIdentifier* const>& names() const {
    return names_;
  }
  const ASTIdentifier* name(int i) const { return names_[i]; }
  const ASTIdentifier* first_name() const { return names_.front(); }
  const ASTIdentifier* last_name() const { return names_.back(); }

  // Return this PathExpression as a dotted SQL identifier string, with
  // quoting if necessary.  If <max_prefix_size> is non-zero, include at most
  // that many identifiers from the prefix of <path>.
  std::string ToIdentifierPathString(size_t max_prefix_size = 0) const;

  // Return the vector of identifier strings (without quoting).
  std::vector<std::string> ToIdentifierVector() const;

  // Similar to ToIdentifierVector(), but returns a vector of IdString's,
  // avoiding the need to make copies.
  std::vector<IdString> ToIdStringVector() const;
      """
    )

  gen.AddNode(
      name='ASTTableExpression',
      tag_id=15,
      parent='ASTNode',
      is_abstract=True,
      comment="""
   Superclass for all table expressions.  These are things that appear in the
   from clause and produce a stream of rows like a table.
   This includes table scans, joins and subqueries.
    """,
      extra_public_defs="""
  bool IsTableExpression() const override { return true; }

  // Return the alias, if the particular subclass has one.
  virtual const ASTAlias* alias() const { return nullptr; }

  // Return the ASTNode location of the alias for this table expression,
  // if applicable.
  const ASTNode* alias_location() const;
      """
    )

  gen.AddNode(
      name='ASTTablePathExpression',
      tag_id=16,
      parent='ASTTableExpression',
      comment="""
   TablePathExpression are the TableExpressions that introduce a single scan,
   referenced by a path expression or UNNEST, and can optionally have
   aliases, hints, and WITH OFFSET.
    """,
      fields=[
          Field(
              'path_expr',
              'ASTPathExpression',
              tag_id=2,
              comment="""
               Exactly one of path_exp or unnest_expr must be non-NULL.
              """),
          Field(
              'unnest_expr',
              'ASTUnnestExpression',
              tag_id=3),
          Field(
              'hint',
              'ASTHint',
              tag_id=4),
          Field(
              'alias',
              'ASTAlias',
              tag_id=5,
              # Existing API getter specifies "override"
              gen_setters_and_getters=False),
          Field(
              'with_offset',
              'ASTWithOffset',
              tag_id=6,
              comment="""
              Present if the scan had WITH OFFSET.
              """),
          Field(
              'pivot_clause',
              'ASTPivotClause',
              tag_id=7,
              comment="""
              At most one of pivot_clause or unpivot_clause can be present.
              """),
          Field(
              'unpivot_clause',
              'ASTUnpivotClause',
              tag_id=8),
          Field(
              'for_system_time',
              'ASTForSystemTime',
              tag_id=9),
          Field(
              'sample_clause',
              'ASTSampleClause',
              tag_id=10),
      ],
      extra_public_defs="""
  const ASTAlias* alias() const override { return alias_; }
      """
    )

  gen.AddNode(
      name='ASTFromClause',
      tag_id=17,
      parent='ASTNode',
      fields=[
          Field(
              'table_expression',
              'ASTTableExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED,
              comment="""
  A FromClause has exactly one TableExpression child.
  If the FROM clause has commas, they will be expressed as a tree
  of ASTJoin nodes with join_type=COMMA.
              """),
      ],
    )

  gen.AddNode(
      name='ASTWhereClause',
      tag_id=18,
      parent='ASTNode',
      fields=[
          Field(
              'expression',
              'ASTExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
      ],
    )

  gen.AddNode(
      name='ASTBooleanLiteral',
      tag_id=19,
      parent='ASTLeaf',
      fields=[
          Field(
              'value',
              SCALAR_BOOL,
              tag_id=2),
      ],
    )

  gen.AddNode(
      name='ASTAndExpr',
      tag_id=20,
      parent='ASTExpression',
      fields=[
          Field(
              'conjuncts',
              'ASTExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REST_AS_REPEATED),
      ],
      extra_public_defs="""
  bool IsAllowedInComparison() const override { return parenthesized(); }
      """
      )

  gen.AddNode(
      name='ASTBinaryExpression',
      tag_id=21,
      parent='ASTExpression',
      use_custom_debug_string=True,
      fields=[
          Field(
              'op',
              SCALAR_BINARY_OP,
              tag_id=2,
              comment="""
              See description of Op values in ast_enums.proto.
              """),
          Field(
              'is_not',
              SCALAR_BOOL,
              tag_id=3,
              comment="""
              Signifies whether the binary operator has a preceding NOT to it.
              For NOT LIKE and IS NOT.
              """),
          Field(
              'lhs',
              'ASTExpression',
              tag_id=4,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'rhs',
              'ASTExpression',
              tag_id=5,
              field_loader=FieldLoaderMethod.REQUIRED),
      ],
      extra_public_defs="""
  // Returns name of the operator in SQL, including the NOT keyword when
  // necessary.
  std::string GetSQLForOperator() const;

  bool IsAllowedInComparison() const override;
      """
      )

  gen.AddNode(
      name='ASTStringLiteral',
      tag_id=22,
      parent='ASTLeaf',
      fields=[
          Field(
              'string_value',
              SCALAR_STRING,
              tag_id=2,
              gen_setters_and_getters=False),
      ],
      extra_public_defs="""
  // The parsed and validated value of this literal. The raw input value can be
  // found in image().
  const std::string& string_value() const { return string_value_; }
  void set_string_value(std::string string_value) {
    string_value_ = std::move(string_value);
  }
       """
      )

  gen.AddNode(
      name='ASTStar',
      tag_id=23,
      parent='ASTLeaf',
      )

  gen.AddNode(
      name='ASTOrExpr',
      tag_id=24,
      parent='ASTExpression',
      fields=[
          Field(
              'disjuncts',
              'ASTExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REST_AS_REPEATED),
      ],
      extra_public_defs="""
  bool IsAllowedInComparison() const override { return parenthesized(); }
      """
      )

  gen.AddNode(
      name='ASTGroupingItem',
      tag_id=25,
      parent='ASTNode',
      comment="""
      Represents a grouping item, which is either an expression (a regular
      group by key) or a rollup list.
      """,
      fields=[
          Field(
              'expression',
              'ASTExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.OPTIONAL_EXPRESSION,
              comment="""
              Exactly one of expression() and rollup() will be non-NULL.
              """),
          Field(
              'rollup',
              'ASTRollup',
              tag_id=3),
      ])

  gen.AddNode(
      name='ASTGroupBy',
      tag_id=26,
      parent='ASTNode',
      fields=[
          Field(
              'hint',
              'ASTHint',
              tag_id=2),
          Field(
              'grouping_items',
              'ASTGroupingItem',
              tag_id=3,
              field_loader=FieldLoaderMethod.REST_AS_REPEATED),
      ])

  gen.AddNode(
      name='ASTOrderingExpression',
      tag_id=27,
      parent='ASTNode',
      use_custom_debug_string=True,
      fields=[
          Field(
              'expression',
              'ASTExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'collate',
              'ASTCollate',
              tag_id=3),
          Field(
              'null_order',
              'ASTNullOrder',
              tag_id=4),
          Field(
              'ordering_spec',
              SCALAR_ORDERING_SPEC,
              tag_id=5)

      ],
      extra_public_defs="""
  bool descending() const { return ordering_spec_ == DESC; }
      """,
  )

  gen.AddNode(
      name='ASTOrderBy',
      tag_id=28,
      parent='ASTNode',
      fields=[
          Field(
              'hint',
              'ASTHint',
              tag_id=2),
          Field(
              'ordering_expressions',
              'ASTOrderingExpression',
              tag_id=3,
              field_loader=FieldLoaderMethod.REST_AS_REPEATED),
      ])

  gen.AddNode(
      name='ASTLimitOffset',
      tag_id=29,
      parent='ASTNode',
      fields=[
          Field(
              'limit',
              'ASTExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED,
              comment="""
          The LIMIT value. Never NULL.
              """),
          Field(
              'offset',
              'ASTExpression',
              tag_id=3,
              field_loader=FieldLoaderMethod.OPTIONAL_EXPRESSION,
              comment="""
          The OFFSET value. NULL if no OFFSET specified.
              """),
      ])

  gen.AddNode(
      name='ASTFloatLiteral',
      tag_id=30,
      parent='ASTLeaf',
      )

  gen.AddNode(
      name='ASTNullLiteral',
      tag_id=31,
      parent='ASTLeaf',
      )

  gen.AddNode(
      name='ASTOnClause',
      tag_id=32,
      parent='ASTNode',
      fields=[
          Field(
              'expression',
              'ASTExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED)
      ])

  gen.AddNode(
      name='ASTWithClauseEntry',
      tag_id=33,
      parent='ASTNode',
      fields=[
          Field(
              'alias',
              'ASTIdentifier',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'query',
              'ASTQuery',
              tag_id=3,
              field_loader=FieldLoaderMethod.REQUIRED)
      ])

  gen.AddNode(
      name='ASTJoin',
      tag_id=34,
      parent='ASTTableExpression',
      use_custom_debug_string=True,
      comment="""
      Joins could introduce multiple scans and cannot have aliases.
      It can also represent a JOIN with a list of consecutive ON/USING
      clauses. Such a JOIN is only for internal use, and will never show up in
      the final parse tree.
      """,
      fields=[
          Field(
              'lhs',
              'ASTTableExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'hint',
              'ASTHint',
              tag_id=3),
          Field(
              'rhs',
              'ASTTableExpression',
              tag_id=4,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'on_clause',
              'ASTOnClause',
              tag_id=5),
          Field(
              'using_clause',
              'ASTUsingClause',
              tag_id=6),
          Field(
              'clause_list',
              'ASTOnOrUsingClauseList',
              tag_id=7,
              gen_setters_and_getters=False,
              private_comment="""
      Note that if consecutive ON/USING clauses are encountered, they are saved
      as clause_list_, and both on_clause_ and using_clause_ will be nullptr.
              """),
          Field(
              'join_type',
              SCALAR_JOIN_TYPE,
              tag_id=8),
          Field(
              'join_hint',
              SCALAR_JOIN_HINT,
              tag_id=9),
          Field(
              'natural',
              SCALAR_BOOL,
              tag_id=10),
          Field(
              'unmatched_join_count',
              SCALAR_INT,
              tag_id=11,
              comment="""
      unmatched_join_count_ and transformation_needed are for internal use for
      handling consecutive ON/USING clauses. They are not used in the final AST.
              """,
              private_comment="""
      The number of qualified joins that do not have a matching ON/USING clause.
      See the comment in join_processor.cc for details.
              """),
          Field(
              'transformation_needed',
              SCALAR_BOOL,
              tag_id=12,
              private_comment="""
      Indicates if this node needs to be transformed. See the comment
      in join_processor.cc for details.
      This is true if contains_clause_list_ is true, or if there is a JOIN with
      ON/USING clause list on the lhs side of the tree path.
      For internal use only. See the comment in join_processor.cc for details.
              """),
          Field(
              'contains_comma_join',
              SCALAR_BOOL,
              tag_id=13,
              private_comment="""
      Indicates whether this join contains a COMMA JOIN on the lhs side of the
      tree path.
              """),
      ],
      extra_public_defs="""
  // Represents a parse error when parsing join expressions.
  // See comments in file join_processor.h for more details.
  struct ParseError {
    // The node where the error occurs.
    const ASTNode* error_node;

    std::string message;
  };

  const ParseError* parse_error() const {
    return parse_error_.get();
  }
  void set_parse_error(std::unique_ptr<ParseError> parse_error) {
    parse_error_ = std::move(parse_error);
  }

  // The join type and hint strings
  std::string GetSQLForJoinType() const;
  std::string GetSQLForJoinHint() const;
       """,
      extra_private_defs="""
  std::unique_ptr<ParseError> parse_error_ = nullptr;
       """
      )

  gen.AddNode(
      name='ASTWithClause',
      tag_id=35,
      parent='ASTNode',
      use_custom_debug_string=True,
      fields=[
          Field(
              'with',
              'ASTWithClauseEntry',
              tag_id=2,
              field_loader=FieldLoaderMethod.REST_AS_REPEATED),
          Field(
              'recursive',
              SCALAR_BOOL,
              tag_id=3)

      ])

  gen.AddNode(
      name='ASTHaving',
      tag_id=36,
      parent='ASTNode',
      fields=[
          Field(
              'expression',
              'ASTExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
      ])

  gen.AddNode(
      name='ASTType',
      tag_id=37,
      parent='ASTNode',
      is_abstract=True,
      extra_public_defs="""
  bool IsType() const override { return true; }

  virtual const ASTTypeParameterList* type_parameters() const = 0;

  virtual const ASTCollate* collate() const = 0;
      """,
      )

  gen.AddNode(
      name='ASTSimpleType',
      tag_id=38,
      parent='ASTType',
      comment="""
 TODO This takes a PathExpression and isn't really a simple type.
 Calling this NamedType or TypeName may be more appropriate.
      """,
      fields=[
          Field(
              'type_name',
              'ASTPathExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'type_parameters',
              'ASTTypeParameterList',
              tag_id=3,
              getter_is_override=True,
              field_loader=FieldLoaderMethod.OPTIONAL),
          Field(
              'collate',
              'ASTCollate',
              tag_id=4,
              field_loader=FieldLoaderMethod.OPTIONAL),
      ])

  gen.AddNode(
      name='ASTArrayType',
      tag_id=39,
      parent='ASTType',
      fields=[
          Field(
              'element_type',
              'ASTType',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'type_parameters',
              'ASTTypeParameterList',
              tag_id=3,
              getter_is_override=True,
              field_loader=FieldLoaderMethod.OPTIONAL),
          Field(
              'collate',
              'ASTCollate',
              tag_id=4,
              getter_is_override=True,
              field_loader=FieldLoaderMethod.OPTIONAL),
      ])

  gen.AddNode(
      name='ASTStructField',
      tag_id=40,
      parent='ASTNode',
      fields=[
          Field(
              'name',
              'ASTIdentifier',
              tag_id=2,
              comment="""
     name_ will be NULL for anonymous fields like in STRUCT<int, string>.
              """),
          Field(
              'type',
              'ASTType',
              tag_id=3,
              field_loader=FieldLoaderMethod.REQUIRED),
      ])

  gen.AddNode(
      name='ASTStructType',
      tag_id=41,
      parent='ASTType',
      fields=[
          Field(
              'struct_fields',
              'ASTStructField',
              tag_id=2,
              field_loader=FieldLoaderMethod.REPEATING_WHILE_IS_NODE_KIND),
          Field(
              'type_parameters',
              'ASTTypeParameterList',
              tag_id=3,
              getter_is_override=True,
              field_loader=FieldLoaderMethod.OPTIONAL),
          Field(
              'collate',
              'ASTCollate',
              tag_id=4,
              getter_is_override=True,
              field_loader=FieldLoaderMethod.OPTIONAL),
      ])

  gen.AddNode(
      name='ASTCastExpression',
      tag_id=42,
      parent='ASTExpression',
      use_custom_debug_string=True,
      fields=[
          Field(
              'expr',
              'ASTExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'type',
              'ASTType',
              tag_id=3,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'format',
              'ASTFormatClause',
              tag_id=4),
          Field(
              'is_safe_cast',
              SCALAR_BOOL,
              tag_id=5),
      ])

  gen.AddNode(
      name='ASTSelectAs',
      tag_id=43,
      parent='ASTNode',
      comment="""
   This represents a SELECT with an AS clause giving it an output type.
     SELECT AS STRUCT ...
     SELECT AS VALUE ...
     SELECT AS <type_name> ...
   Exactly one of these is present.
      """,
      use_custom_debug_string=True,
      fields=[
          Field(
              'type_name',
              'ASTPathExpression',
              tag_id=2),
          Field(
              'as_mode',
              SCALAR_AS_MODE,
              tag_id=3,
              comment="""
              Set if as_mode() == kTypeName;
              """),
      ],
      extra_public_defs="""

  bool is_select_as_struct() const { return as_mode_ == STRUCT; }
  bool is_select_as_value() const { return as_mode_ == VALUE; }
      """
      )

  gen.AddNode(
      name='ASTRollup',
      tag_id=44,
      parent='ASTNode',
      fields=[
          Field(
              'expressions',
              'ASTExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REST_AS_REPEATED),
      ])

  gen.AddNode(
      name='ASTFunctionCall',
      tag_id=45,
      parent='ASTExpression',
      use_custom_debug_string=True,
      fields=[
          Field(
              'function',
              'ASTPathExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'arguments',
              'ASTExpression',
              tag_id=3,
              field_loader=FieldLoaderMethod.REPEATING_WHILE_IS_EXPRESSION),
          Field(
              'having_modifier',
              'ASTHavingModifier',
              tag_id=4,
              private_comment="""
       Set if the function was called with FUNC(args HAVING {MAX|MIN} expr).
              """),
          Field(
              'clamped_between_modifier',
              'ASTClampedBetweenModifier',
              tag_id=5,
              comment="""
      If present, applies to the inputs of anonymized aggregate functions.
              """,
              private_comment="""
      Set if the function was called with
      FUNC(args CLAMPED BETWEEN low AND high).
              """),
          Field(
              'with_report_modifier',
              'ASTWithReportModifier',
              tag_id=13,
              comment="""
      If present, the report modifier applies to the result of anonymized
      aggregate functions.
              """,
              private_comment="""
      Set if the function was called with
      FUNC(args WITH REPORT).
              """),
          Field(
              'order_by',
              'ASTOrderBy',
              tag_id=6,
              comment="""
      If present, applies to the inputs of aggregate functions.
              """,
              private_comment="""
      Set if the function was called with FUNC(args ORDER BY cols).
              """),
          Field(
              'limit_offset',
              'ASTLimitOffset',
              tag_id=7,
              comment="""
      If present, this applies to the inputs of aggregate functions.
              """,
              private_comment="""
      Set if the function was called with FUNC(args LIMIT N).
              """),
          Field(
              'hint',
              'ASTHint',
              tag_id=8,
              comment="""
      hint if not null.
              """,
              private_comment="""
              Optional hint.
              """),
          Field(
              'with_group_rows',
              'ASTWithGroupRows',
              tag_id=9,
              private_comment="""
      Set if the function was called WITH GROUP_ROWS(...).
              """),
          Field(
              'null_handling_modifier',
              SCALAR_NULL_HANDLING_MODIFIER,
              tag_id=10,
              comment="""
      If present, modifies the input behavior of aggregate functions.
              """,
              private_comment="""
      Set if the function was called with FUNC(args {IGNORE|RESPECT} NULLS).
              """),
          Field(
              'distinct',
              SCALAR_BOOL,
              tag_id=11,
              private_comment="""
      True if the function was called with FUNC(DISTINCT args).
              """),
          Field(
              'is_current_date_time_without_parentheses',
              SCALAR_BOOL,
              tag_id=12,
              comment="""
      Used by the Bison parser to mark CURRENT_<date/time> functions to which no
      parentheses have yet been applied.
              """,
              private_comment="""
      This is set by the Bison parser to indicate a parentheses-less call to
      CURRENT_* functions. The parser parses them as function calls even without
      the parentheses, but then still allows function call parentheses to be
      applied.
              """),
      ],
      extra_public_defs="""
  // Convenience method that returns true if any modifiers are set. Useful for
  // places in the resolver where function call syntax is used for purposes
  // other than a function call (e.g., <array>[OFFSET(<expr>) or WEEK(MONDAY)]).
  bool HasModifiers() const {
    return distinct_ || null_handling_modifier_ != DEFAULT_NULL_HANDLING ||
           having_modifier_ != nullptr ||
           clamped_between_modifier_ != nullptr || order_by_ != nullptr ||
           limit_offset_ != nullptr || with_group_rows_ != nullptr;
  }
      """)

  gen.AddNode(
      name='ASTArrayConstructor',
      tag_id=46,
      parent='ASTExpression',
      fields=[
          Field(
              'type',
              'ASTArrayType',
              tag_id=2,
              comment="""
              May return NULL. Occurs only if the array is constructed through
              ARRAY<type>[...] syntax and not ARRAY[...] or [...].
          """),
          Field(
              'elements',
              'ASTExpression',
              tag_id=3,
              field_loader=FieldLoaderMethod.REST_AS_REPEATED),
      ],
      # legacy code uses element() instead of elements() for getter
      extra_public_defs="""
  // DEPRECATED - use elements(int i)
  const ASTExpression* element(int i) const { return elements_[i]; }
      """)

  gen.AddNode(
      name='ASTStructConstructorArg',
      tag_id=47,
      parent='ASTNode',
      fields=[
          Field(
              'expression',
              'ASTExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'alias',
              'ASTAlias',
              tag_id=3,
              field_loader=FieldLoaderMethod.OPTIONAL),
      ])

  gen.AddNode(
      name='ASTStructConstructorWithParens',
      tag_id=48,
      parent='ASTExpression',
      comment="""
      This node results from structs constructed with (expr, expr, ...).
      This will only occur when there are at least two expressions.
      """,
      fields=[
          Field(
              'field_expressions',
              'ASTExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REST_AS_REPEATED),
      ])

  gen.AddNode(
      name='ASTStructConstructorWithKeyword',
      tag_id=49,
      parent='ASTExpression',
      comment="""
      This node results from structs constructed with the STRUCT keyword.
        STRUCT(expr [AS alias], ...)
        STRUCT<...>(expr [AS alias], ...)
      Both forms support empty field lists.
      The struct_type_ child will be non-NULL for the second form,
      which includes the struct's field list.
      """,
      fields=[
          Field(
              'struct_type',
              'ASTStructType',
              tag_id=2,
              private_comment="""
              May be NULL.
              """),
          Field(
              'fields',
              'ASTStructConstructorArg',
              tag_id=3,
              field_loader=FieldLoaderMethod.REST_AS_REPEATED),
      ],
      extra_public_defs="""
  // Deprecated - use fields(int i)
  const ASTStructConstructorArg* field(int idx) const { return fields_[idx]; }
      """)

  gen.AddNode(
      name='ASTInExpression',
      tag_id=50,
      parent='ASTExpression',
      use_custom_debug_string=True,
      fields=[
          Field(
              'lhs',
              'ASTExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED,
              private_comment="""
      Expression for which we need to verify whether its resolved result matches
      any of the resolved results of the expressions present in the in_list_.
              """),
          Field(
              'hint',
              'ASTHint',
              tag_id=3,
              comment="""
      Hints specified on IN clause.
      This can be set only if IN clause has subquery as RHS.
              """,
              private_comment="""
      Hints specified on IN clause
              """),
          Field(
              'in_list',
              'ASTInList',
              tag_id=4,
              comment="""
      Exactly one of in_list, query or unnest_expr is present.
              """,
              private_comment="""
      List of expressions to check against for the presence of lhs_.
              """),
          Field(
              'query',
              'ASTQuery',
              tag_id=5,
              private_comment="""
      Query returns the row values to check against for the presence of lhs_.
              """),
          Field(
              'unnest_expr',
              'ASTUnnestExpression',
              tag_id=6,
              private_comment="""
      Check if lhs_ is an element of the array value inside Unnest.
              """),
          Field(
              'is_not',
              SCALAR_BOOL,
              tag_id=7,
              comment="""
      Signifies whether the IN operator has a preceding NOT to it.
              """),
      ],
      extra_public_defs="""
  bool IsAllowedInComparison() const override { return parenthesized(); }
      """
      )

  gen.AddNode(
      name='ASTInList',
      tag_id=51,
      parent='ASTNode',
      comment="""
      This implementation is shared with the IN operator and LIKE ANY/SOME/ALL.
      """,
      fields=[
          Field(
              'list',
              'ASTExpression',
              tag_id=2,
              private_comment="""
              List of expressions present in the InList node.
              """,
              field_loader=FieldLoaderMethod.REST_AS_REPEATED),
      ])

  gen.AddNode(
      name='ASTBetweenExpression',
      tag_id=52,
      parent='ASTExpression',
      use_custom_debug_string=True,
      fields=[
          Field(
              'lhs',
              'ASTExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED,
              private_comment="""
               Represents <lhs_> BETWEEN <low_> AND <high_>
              """),
          Field(
              'low',
              'ASTExpression',
              tag_id=3,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'high',
              'ASTExpression',
              tag_id=4,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'is_not',
              SCALAR_BOOL,
              tag_id=5,
              comment="""
              Signifies whether the BETWEEN operator has a preceding NOT to it.
              """),
      ],
      extra_public_defs="""
  bool IsAllowedInComparison() const override { return parenthesized(); }
      """)

  gen.AddNode(
      name='ASTNumericLiteral',
      tag_id=53,
      parent='ASTLeaf')

  gen.AddNode(
      name='ASTBigNumericLiteral',
      tag_id=54,
      parent='ASTLeaf')

  gen.AddNode(
      name='ASTBytesLiteral',
      tag_id=55,
      parent='ASTLeaf',
      extra_public_defs="""
  // The parsed and validated value of this literal. The raw input value can be
  // found in image().
  const std::string& bytes_value() const { return bytes_value_; }
  void set_bytes_value(std::string bytes_value) {
    bytes_value_ = std::move(bytes_value);
  }
      """,
      extra_private_defs="""
  std::string bytes_value_;
      """)

  gen.AddNode(
      name='ASTDateOrTimeLiteral',
      tag_id=56,
      parent='ASTExpression',
      use_custom_debug_string=True,
      fields=[
          Field(
              'string_literal',
              'ASTStringLiteral',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'type_kind',
              SCALAR_TYPE_KIND,
              tag_id=3),
      ])

  gen.AddNode(
      name='ASTMaxLiteral',
      tag_id=57,
      parent='ASTLeaf',
      comment="""
      This represents the value MAX that shows up in type parameter lists.
      It will not show up as a general expression anywhere else.
      """)

  gen.AddNode(
      name='ASTJSONLiteral',
      tag_id=58,
      parent='ASTLeaf')

  gen.AddNode(
      name='ASTCaseValueExpression',
      tag_id=59,
      parent='ASTExpression',
      fields=[
          Field(
              'arguments',
              'ASTExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REST_AS_REPEATED),
      ])

  gen.AddNode(
      name='ASTCaseNoValueExpression',
      tag_id=60,
      parent='ASTExpression',
      fields=[
          Field(
              'arguments',
              'ASTExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REST_AS_REPEATED),
      ])

  gen.AddNode(
      name='ASTArrayElement',
      tag_id=61,
      parent='ASTGeneralizedPathExpression',
      fields=[
          Field(
              'array',
              'ASTExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'position',
              'ASTExpression',
              tag_id=3,
              field_loader=FieldLoaderMethod.REQUIRED),
      ])

  gen.AddNode(
      name='ASTBitwiseShiftExpression',
      tag_id=62,
      parent='ASTExpression',
      use_custom_debug_string=True,
      fields=[
          Field(
              'lhs',
              'ASTExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'rhs',
              'ASTExpression',
              tag_id=3,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'is_left_shift',
              SCALAR_BOOL,
              tag_id=4,
              comment="""
         Signifies whether the bitwise shift is of left shift type "<<" or right
         shift type ">>".
              """),
      ])

  gen.AddNode(
      name='ASTCollate',
      tag_id=63,
      parent='ASTNode',
      fields=[
          Field(
              'collation_name',
              'ASTExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
      ])

  gen.AddNode(
      name='ASTDotGeneralizedField',
      tag_id=64,
      parent='ASTGeneralizedPathExpression',
      comment="""
      This is a generalized form of extracting a field from an expression.
      It uses a parenthesized path_expression instead of a single identifier
      to select the field.
      """
      ,
      fields=[
          Field(
              'expr',
              'ASTExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'path',
              'ASTPathExpression',
              tag_id=3,
              field_loader=FieldLoaderMethod.REQUIRED),
      ])

  gen.AddNode(
      name='ASTDotIdentifier',
      tag_id=65,
      parent='ASTGeneralizedPathExpression',
      comment="""
   This is used for using dot to extract a field from an arbitrary expression.
   In cases where we know the left side is always an identifier path, we
   use ASTPathExpression instead.
      """,
      fields=[
          Field(
              'expr',
              'ASTExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'name',
              'ASTIdentifier',
              tag_id=3,
              field_loader=FieldLoaderMethod.REQUIRED),
      ])

  gen.AddNode(
      name='ASTDotStar',
      tag_id=66,
      parent='ASTExpression',
      fields=[
          Field(
              'expr',
              'ASTExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
      ])

  gen.AddNode(
      name='ASTDotStarWithModifiers',
      tag_id=67,
      parent='ASTExpression',
      comment="""
      SELECT x.* EXCEPT(...) REPLACE(...).  See (broken link).
      """,
      fields=[
          Field(
              'expr',
              'ASTExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'modifiers',
              'ASTStarModifiers',
              tag_id=3,
              field_loader=FieldLoaderMethod.REQUIRED),
      ])

  gen.AddNode(
      name='ASTExpressionSubquery',
      tag_id=68,
      parent='ASTExpression',
      use_custom_debug_string=True,
      comment="""
      A subquery in an expression.  (Not in the FROM clause.)
      """,
      fields=[
          Field(
              'hint',
              'ASTHint',
              tag_id=2),
          Field(
              'query',
              'ASTQuery',
              tag_id=3,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'modifier',
              SCALAR_MODIFIER,
              tag_id=4,
              comment="""
              The syntactic modifier on this expression subquery.
              """),
      ],
      extra_public_defs="""
  static std::string ModifierToString(Modifier modifier);

  // Note, this is intended by called from inside bison_parser.  At this stage
  // InitFields has _not_ been set, thus we need to use only children offsets.
  // Returns null on error.
  ASTQuery* GetMutableQueryChildInternal() {
    if (num_children() == 1) {
      return mutable_child(0)->GetAsOrNull<ASTQuery>();
    } else if (num_children() == 2) {
      // Hint is the first child.
      return mutable_child(1)->GetAsOrNull<ASTQuery>();
    } else {
      return nullptr;
    }
  }
      """)

  gen.AddNode(
      name='ASTExtractExpression',
      tag_id=69,
      parent='ASTExpression',
      fields=[
          Field(
              'lhs_expr',
              'ASTExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'rhs_expr',
              'ASTExpression',
              tag_id=3,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'time_zone_expr',
              'ASTExpression',
              tag_id=4,
              field_loader=FieldLoaderMethod.OPTIONAL_EXPRESSION),
      ])

  gen.AddNode(
      name='ASTHavingModifier',
      tag_id=70,
      parent='ASTNode',
      fields=[
          Field(
              'expr',
              'ASTExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED,
              private_comment="""
              The expression MAX or MIN applies to. Never NULL.
              """),
          Field(
              'modifier_kind',
              SCALAR_MODIFIER_KIND,
              tag_id=3),
      ])

  gen.AddNode(
      name='ASTIntervalExpr',
      tag_id=71,
      parent='ASTExpression',
      fields=[
          Field(
              'interval_value',
              'ASTExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'date_part_name',
              'ASTIdentifier',
              tag_id=3,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'date_part_name_to',
              'ASTIdentifier',
              tag_id=4),
      ])

  gen.AddNode(
      name='ASTNamedArgument',
      tag_id=72,
      parent='ASTExpression',
      comment="""
     Represents a named function call argument using syntax: name => expression.
     The resolver will match these against available argument names in the
     function signature.
      """,
      fields=[
          Field(
              'name',
              'ASTIdentifier',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED,
              private_comment="""
              Required, never NULL.
              """),
          Field(
              'expr',
              'ASTExpression',
              tag_id=3,
              field_loader=FieldLoaderMethod.REQUIRED,
              private_comment="""
              Required, never NULL.
              """),
      ])

  gen.AddNode(
      name='ASTNullOrder',
      tag_id=73,
      parent='ASTNode',
      use_custom_debug_string=True,
      fields=[
          Field(
              'nulls_first',
              SCALAR_BOOL,
              tag_id=2),
      ])

  gen.AddNode(
      name='ASTOnOrUsingClauseList',
      tag_id=74,
      parent='ASTNode',
      fields=[
          Field(
              'on_or_using_clause_list',
              'ASTNode',
              tag_id=2,
              field_loader=FieldLoaderMethod.REST_AS_REPEATED,
              private_comment="""
          Each element in the list must be either ASTOnClause or ASTUsingClause.
              """),
      ])

  gen.AddNode(
      name='ASTParenthesizedJoin',
      tag_id=75,
      parent='ASTTableExpression',
      fields=[
          Field(
              'join',
              'ASTJoin',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED,
              private_comment="""
              Required.
              """),
          Field(
              'sample_clause',
              'ASTSampleClause',
              tag_id=3,
              private_comment="""
              Optional.
              """),
      ])

  gen.AddNode(
      name='ASTPartitionBy',
      tag_id=76,
      parent='ASTNode',
      fields=[
          Field(
              'hint',
              'ASTHint',
              tag_id=2),
          Field(
              'partitioning_expressions',
              'ASTExpression',
              tag_id=3,
              field_loader=FieldLoaderMethod.REST_AS_REPEATED),
      ])

  gen.AddNode(
      name='ASTSetOperation',
      tag_id=77,
      parent='ASTQueryExpression',
      use_custom_debug_string=True,
      fields=[
          Field(
              'hint',
              'ASTHint',
              tag_id=2),
          Field(
              'inputs',
              'ASTQueryExpression',
              tag_id=3,
              field_loader=FieldLoaderMethod.REST_AS_REPEATED),
          Field(
              'op_type',
              SCALAR_OPERATION_TYPE,
              tag_id=4),
          Field(
              'distinct',
              SCALAR_BOOL,
              tag_id=5),
      ],
      extra_public_defs="""
  std::pair<std::string, std::string> GetSQLForOperationPair() const;

  // Returns the SQL keywords for the underlying set operation eg. UNION ALL,
  // UNION DISTINCT, EXCEPT ALL, INTERSECT DISTINCT etc.
  std::string GetSQLForOperation() const;
      """
      )

  gen.AddNode(
      name='ASTStarExceptList',
      tag_id=78,
      parent='ASTNode',
      fields=[
          Field(
              'identifiers',
              'ASTIdentifier',
              tag_id=2,
              field_loader=FieldLoaderMethod.REST_AS_REPEATED),
      ])

  gen.AddNode(
      name='ASTStarModifiers',
      tag_id=79,
      parent='ASTNode',
      comment="""
      SELECT * EXCEPT(...) REPLACE(...).  See (broken link).
      """,
      fields=[
          Field(
              'except_list',
              'ASTStarExceptList',
              tag_id=2),
          Field(
              'replace_items',
              'ASTStarReplaceItem',
              tag_id=3,
              field_loader=FieldLoaderMethod.REST_AS_REPEATED),
      ])

  gen.AddNode(
      name='ASTStarReplaceItem',
      tag_id=80,
      parent='ASTNode',
      fields=[
          Field(
              'expression',
              'ASTExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'alias',
              'ASTIdentifier',
              tag_id=3,
              field_loader=FieldLoaderMethod.REQUIRED),
      ])

  gen.AddNode(
      name='ASTStarWithModifiers',
      tag_id=81,
      parent='ASTExpression',
      comment="""
      SELECT * EXCEPT(...) REPLACE(...).  See (broken link).
      """,
      fields=[
          Field(
              'modifiers',
              'ASTStarModifiers',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
      ])

  gen.AddNode(
      name='ASTTableSubquery',
      tag_id=82,
      parent='ASTTableExpression',
      extra_public_defs="""
  const ASTAlias* alias() const override { return alias_; }
      """,
      fields=[
          Field(
              'subquery',
              'ASTQuery',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'alias',
              'ASTAlias',
              tag_id=3,
              gen_setters_and_getters=False),
          Field(
              'pivot_clause',
              'ASTPivotClause',
              tag_id=4,
              private_comment="""
              One of pivot_clause or unpivot_clause can be present but not both.
              """),
          Field(
              'unpivot_clause',
              'ASTUnpivotClause',
              tag_id=5),
          Field(
              'sample_clause',
              'ASTSampleClause',
              tag_id=6),
      ])

  gen.AddNode(
      name='ASTUnaryExpression',
      tag_id=83,
      parent='ASTExpression',
      use_custom_debug_string=True,
      fields=[
          Field(
              'operand',
              'ASTExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'op',
              SCALAR_UNARY_OP,
              tag_id=3),
      ],
      extra_public_defs="""
  bool IsAllowedInComparison() const override {
    return parenthesized() || op_ != NOT;
  }

  std::string GetSQLForOperator() const;
      """)

  gen.AddNode(
      name='ASTUnnestExpression',
      tag_id=84,
      parent='ASTNode',
      fields=[
          Field(
              'expression',
              'ASTExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
      ])

  gen.AddNode(
      name='ASTWindowClause',
      tag_id=85,
      parent='ASTNode',
      fields=[
          Field(
              'windows',
              'ASTWindowDefinition',
              tag_id=2,
              field_loader=FieldLoaderMethod.REST_AS_REPEATED),
      ])

  gen.AddNode(
      name='ASTWindowDefinition',
      tag_id=86,
      parent='ASTNode',
      fields=[
          Field(
              'name',
              'ASTIdentifier',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED,
              private_comment="""
              Required, never NULL.
              """),
          Field(
              'window_spec',
              'ASTWindowSpecification',
              tag_id=3,
              field_loader=FieldLoaderMethod.REQUIRED,
              private_comment="""
              Required, never NULL.
              """),
      ])

  gen.AddNode(
      name='ASTWindowFrame',
      tag_id=87,
      parent='ASTNode',
      use_custom_debug_string=True,
      fields=[
          Field(
              'start_expr',
              'ASTWindowFrameExpr',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED,
              private_comment="""
              Starting boundary expression. Never NULL.
              """),
          Field(
              'end_expr',
              'ASTWindowFrameExpr',
              tag_id=3,
              private_comment="""
              Ending boundary expression. Can be NULL.
              When this is NULL, the implicit ending boundary is CURRENT ROW.
              """),
          Field(
              'frame_unit',
              SCALAR_FRAME_UNIT,
              tag_id=4,
              gen_setters_and_getters=False),
      ],
      extra_public_defs="""
  void set_unit(FrameUnit frame_unit) { frame_unit_ = frame_unit; }
  FrameUnit frame_unit() const { return frame_unit_; }

  std::string GetFrameUnitString() const;

  static std::string FrameUnitToString(FrameUnit unit);
      """)

  gen.AddNode(
      name='ASTWindowFrameExpr',
      tag_id=88,
      parent='ASTNode',
      use_custom_debug_string=True,
      fields=[
          Field(
              'expression',
              'ASTExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.OPTIONAL_EXPRESSION,
              private_comment="""
             Expression to specify the boundary as a logical or physical offset
             to current row. Cannot be NULL if boundary_type is OFFSET_PRECEDING
             or OFFSET_FOLLOWING; otherwise, should be NULL.
              """),
          Field(
              'boundary_type',
              SCALAR_BOUNDARY_TYPE,
              tag_id=3),
      ],
      extra_public_defs="""
  std::string GetBoundaryTypeString() const;
  static std::string BoundaryTypeToString(BoundaryType type);
      """)

  gen.AddNode(
      name='ASTLikeExpression',
      tag_id=89,
      parent='ASTExpression',
      use_custom_debug_string=True,
      fields=[
          Field(
              'lhs',
              'ASTExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED,
              private_comment="""
      Expression for which we need to verify whether its resolved result matches
      any of the resolved results of the expressions present in the in_list_.
              """),
          Field(
              'op',
              'ASTAnySomeAllOp',
              tag_id=3,
              field_loader=FieldLoaderMethod.REQUIRED,
              comment="""
      The any, some, or all operation used.
              """,
              private_comment="""
      Any, some, or all operator.
              """),
          Field(
              'hint',
              'ASTHint',
              tag_id=4,
              comment="""
      Hints specified on LIKE clause.
      This can be set only if LIKE clause has subquery as RHS.
              """,
              private_comment="""
       Hints specified on LIKE clause
              """),
          Field(
              'in_list',
              'ASTInList',
              tag_id=5,
              comment="""
       Exactly one of in_list, query or unnest_expr is present
              """,
              private_comment="""
       List of expressions to check against for any/some/all comparison for lhs_.
              """),
          Field(
              'query',
              'ASTQuery',
              tag_id=6,
              private_comment="""
       Query returns the row values to check against for any/some/all comparison
       for lhs_.
              """),
          Field(
              'unnest_expr',
              'ASTUnnestExpression',
              tag_id=7,
              private_comment="""
       Check if lhs_ is an element of the array value inside Unnest.
              """),
          Field(
              'is_not',
              SCALAR_BOOL,
              tag_id=8,
              comment="""
       Signifies whether the LIKE operator has a preceding NOT to it.
              """),
      ],
      extra_public_defs="""
  bool IsAllowedInComparison() const override { return parenthesized(); }
      """)

  gen.AddNode(
      name='ASTWindowSpecification',
      tag_id=90,
      parent='ASTNode',
      fields=[
          Field(
              'base_window_name',
              'ASTIdentifier',
              tag_id=2,
              private_comment="""
              All fields are optional, can be NULL.
              """),
          Field(
              'partition_by',
              'ASTPartitionBy',
              tag_id=3),
          Field(
              'order_by',
              'ASTOrderBy',
              tag_id=4),
          Field(
              'window_frame',
              'ASTWindowFrame',
              tag_id=5),
      ])

  gen.AddNode(
      name='ASTWithOffset',
      tag_id=91,
      parent='ASTNode',
      fields=[
          Field(
              'alias',
              'ASTAlias',
              tag_id=2,
              comment="""
               alias may be NULL.
              """),
      ])

  gen.AddNode(
      name='ASTAnySomeAllOp',
      tag_id=92,
      parent='ASTNode',
      use_custom_debug_string=True,
      fields=[
          Field(
              'op',
              SCALAR_ANY_SOME_ALL_OP,
              tag_id=2),
      ],
      extra_public_defs="""
  std::string GetSQLForOperator() const;
      """)

  gen.AddNode(
      name='ASTParameterExprBase',
      tag_id=93,
      parent='ASTExpression',
      is_abstract=True)

  gen.AddNode(
      name='ASTStatementList',
      tag_id=94,
      parent='ASTNode',
      comment="""
      Contains a list of statements.  Variable declarations allowed only at the
      start of the list, and only if variable_declarations_allowed() is true.
      """,
      fields=[
          Field(
              'statement_list',
              'ASTStatement',
              tag_id=2,
              field_loader=FieldLoaderMethod.REST_AS_REPEATED,
              private_comment="""
              Repeated
              """),
          Field(
              'variable_declarations_allowed',
              SCALAR_BOOL,
              tag_id=3),
      ])

  gen.AddNode(
      name='ASTScriptStatement',
      tag_id=95,
      parent='ASTStatement',
      is_abstract=True,
      extra_public_defs="""
  bool IsScriptStatement() const final { return true; }
  bool IsSqlStatement() const override { return false; }
      """)

  gen.AddNode(
      name='ASTHintedStatement',
      tag_id=96,
      parent='ASTStatement',
      comment="""
      This wraps any other statement to add statement-level hints.
      """,
      fields=[
          Field(
              'hint',
              'ASTHint',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'statement',
              'ASTStatement',
              tag_id=3,
              field_loader=FieldLoaderMethod.REQUIRED),
      ])

  gen.AddNode(
      name='ASTExplainStatement',
      tag_id=97,
      parent='ASTStatement',
      comment="""
      Represents an EXPLAIN statement.
      """,
      fields=[
          Field(
              'statement',
              'ASTStatement',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
      ])

  gen.AddNode(
      name='ASTDescribeStatement',
      tag_id=98,
      parent='ASTStatement',
      comment="""
      Represents a DESCRIBE statement.
      """,
      fields=[
          Field(
              'optional_identifier',
              'ASTIdentifier',
              tag_id=2),
          Field(
              'name',
              'ASTPathExpression',
              tag_id=3,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'optional_from_name',
              'ASTPathExpression',
              tag_id=4),
      ])

  gen.AddNode(
      name='ASTShowStatement',
      tag_id=99,
      parent='ASTStatement',
      comment="""
      Represents a SHOW statement.
      """,
      fields=[
          Field(
              'identifier',
              'ASTIdentifier',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'optional_name',
              'ASTPathExpression',
              tag_id=3),
          Field(
              'optional_like_string',
              'ASTStringLiteral',
              tag_id=4),
      ])

  gen.AddNode(
      name='ASTTransactionMode',
      tag_id=100,
      parent='ASTNode',
      is_abstract=True,
      comment="""
      Base class transaction modifier elements.
      """)

  gen.AddNode(
      name='ASTTransactionIsolationLevel',
      tag_id=101,
      parent='ASTTransactionMode',
      fields=[
          Field(
              'identifier1',
              'ASTIdentifier',
              tag_id=2),
          Field(
              'identifier2',
              'ASTIdentifier',
              tag_id=3,
              comment="""
         Second identifier can be non-null only if first identifier is non-null.
               """)
      ])

  gen.AddNode(
      name='ASTTransactionReadWriteMode',
      tag_id=102,
      parent='ASTTransactionMode',
      fields=[
          Field(
              'mode',
              SCALAR_READ_WRITE_MODE,
              tag_id=2),
      ])

  gen.AddNode(
      name='ASTTransactionModeList',
      tag_id=103,
      parent='ASTNode',
      fields=[
          Field(
              'elements',
              'ASTTransactionMode',
              tag_id=2,
              field_loader=FieldLoaderMethod.REST_AS_REPEATED),
      ])

  gen.AddNode(
      name='ASTBeginStatement',
      tag_id=104,
      parent='ASTStatement',
      comment="""
      Represents a BEGIN or START TRANSACTION statement.
      """,
      fields=[
          Field(
              'mode_list',
              'ASTTransactionModeList',
              tag_id=2),
      ])

  gen.AddNode(
      name='ASTSetTransactionStatement',
      tag_id=105,
      parent='ASTStatement',
      comment="""
      Represents a SET TRANSACTION statement.
      """,
      fields=[
          Field(
              'mode_list',
              'ASTTransactionModeList',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
      ])

  gen.AddNode(
      name='ASTCommitStatement',
      tag_id=106,
      parent='ASTStatement',
      comment="""
      Represents a COMMIT statement.
      """)

  gen.AddNode(
      name='ASTRollbackStatement',
      tag_id=107,
      parent='ASTStatement',
      comment="""
      Represents a ROLLBACK statement.
      """)

  gen.AddNode(
      name='ASTStartBatchStatement',
      tag_id=108,
      parent='ASTStatement',
      fields=[
          Field(
              'batch_type',
              'ASTIdentifier',
              tag_id=2),
      ])

  gen.AddNode(
      name='ASTRunBatchStatement',
      tag_id=109,
      parent='ASTStatement',
      )

  gen.AddNode(
      name='ASTAbortBatchStatement',
      tag_id=110,
      parent='ASTStatement',
      )

  gen.AddNode(
      name='ASTDdlStatement',
      tag_id=111,
      parent='ASTStatement',
      is_abstract=True,
      comment="""
      Common superclass of DDL statements.
      """,
      extra_public_defs="""
  bool IsDdlStatement() const override { return true; }

  virtual const ASTPathExpression* GetDdlTarget() const = 0;
      """
      )

  gen.AddNode(
      name='ASTDropEntityStatement',
      tag_id=112,
      parent='ASTDdlStatement',
      use_custom_debug_string=True,
      custom_debug_string_comment="""
      This adds the "if exists" modifier to the node name.
      """,
      comment="""
      Generic DROP statement (broken link).
      """,
      fields=[
          Field(
              'entity_type',
              'ASTIdentifier',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'name',
              'ASTPathExpression',
              tag_id=3,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'is_if_exists',
              SCALAR_BOOL,
              tag_id=4),
      ],
      extra_public_defs="""
  const ASTPathExpression* GetDdlTarget() const override { return name_; }
      """)

  gen.AddNode(
      name='ASTDropFunctionStatement',
      tag_id=113,
      parent='ASTDdlStatement',
      use_custom_debug_string=True,
      custom_debug_string_comment="""
      This adds the "if exists" modifier to the node name.
      """,
      comment="""
      Represents a DROP FUNCTION statement.
      """,
      fields=[
          Field(
              'name',
              'ASTPathExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'parameters',
              'ASTFunctionParameters',
              tag_id=3),
          Field(
              'is_if_exists',
              SCALAR_BOOL,
              tag_id=4),
      ],
      extra_public_defs="""
  const ASTPathExpression* GetDdlTarget() const override { return name_; }
      """)

  gen.AddNode(
      name='ASTDropTableFunctionStatement',
      tag_id=114,
      parent='ASTDdlStatement',
      use_custom_debug_string=True,
      custom_debug_string_comment="""
      This adds the "if exists" modifier to the node name.
      """,
      comment="""
      Represents a DROP TABLE FUNCTION statement.
      Note: Table functions don't support overloading so function parameters are
            not accepted in this statement.
            (broken link)
      """,
      fields=[
          Field(
              'name',
              'ASTPathExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'is_if_exists',
              SCALAR_BOOL,
              tag_id=3),
      ],
      extra_public_defs="""
  const ASTPathExpression* GetDdlTarget() const override { return name_; }
      """)

  gen.AddNode(
      name='ASTDropAllRowAccessPoliciesStatement',
      tag_id=115,
      parent='ASTStatement',
      comment="""
      Represents a DROP ALL ROW ACCESS POLICIES statement.
      """,
      fields=[
          Field(
              'table_name',
              'ASTPathExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'has_access_keyword',
              SCALAR_BOOL,
              tag_id=3),
      ])

  gen.AddNode(
      name='ASTDropMaterializedViewStatement',
      tag_id=116,
      parent='ASTDdlStatement',
      use_custom_debug_string=True,
      custom_debug_string_comment="""
      This adds the "if exists" modifier to the node name.
      """,
      comment="""
      Represents a DROP MATERIALIZED VIEW statement.
      """,
      fields=[
          Field(
              'name',
              'ASTPathExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'is_if_exists',
              SCALAR_BOOL,
              tag_id=3),
      ],
      extra_public_defs="""
  const ASTPathExpression* GetDdlTarget() const override { return name_; }
      """)

  gen.AddNode(
      name='ASTDropSnapshotTableStatement',
      tag_id=117,
      parent='ASTDdlStatement',
      use_custom_debug_string=True,
      custom_debug_string_comment="""
      This adds the "if exists" modifier to the node name.
      """,
      comment="""
      Represents a DROP SNAPSHOT TABLE statement.
      """,
      fields=[
          Field(
              'name',
              'ASTPathExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'is_if_exists',
              SCALAR_BOOL,
              tag_id=3),
      ],
      extra_public_defs="""
  const ASTPathExpression* GetDdlTarget() const override { return name_; }
      """)

  gen.AddNode(
      name='ASTDropSearchIndexStatement',
      tag_id=118,
      parent='ASTDdlStatement',
      use_custom_debug_string=True,
      custom_debug_string_comment="""
      This adds the "if exists" modifier to the node name.
      """,
      comment="""
      Represents a DROP SEARCH INDEX statement.
      """,
      fields=[
          Field(
              'name',
              'ASTPathExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'table_name',
              'ASTPathExpression',
              tag_id=3),
          Field(
              'is_if_exists',
              SCALAR_BOOL,
              tag_id=4),
      ],
      extra_public_defs="""
  const ASTPathExpression* GetDdlTarget() const override { return name_; }
      """)

  gen.AddNode(
      name='ASTRenameStatement',
      tag_id=119,
      parent='ASTStatement',
      comment="""
      Represents a RENAME statement.
      """,
      fields=[
          Field(
              'identifier',
              'ASTIdentifier',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'old_name',
              'ASTPathExpression',
              tag_id=3,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'new_name',
              'ASTPathExpression',
              tag_id=4,
              field_loader=FieldLoaderMethod.REQUIRED),
      ])

  gen.AddNode(
      name='ASTImportStatement',
      tag_id=120,
      parent='ASTStatement',
      comment="""
      Represents an IMPORT statement, which currently support MODULE or PROTO
      kind. We want this statement to be a generic import at some point.
      """,
      fields=[
          Field(
              'name',
              'ASTPathExpression',
              tag_id=2,
              private_comment="""
              Exactly one of 'name_' or 'string_value_' will be populated.
              """),
          Field(
              'string_value',
              'ASTStringLiteral',
              tag_id=3),
          Field(
              'alias',
              'ASTAlias',
              tag_id=4,
              private_comment="""
              At most one of 'alias_' or 'into_alias_' will be populated.
              """),
          Field(
              'into_alias',
              'ASTIntoAlias',
              tag_id=5),
          Field(
              'options_list',
              'ASTOptionsList',
              tag_id=6,
              private_comment="""
              May be NULL.
              """),
          Field(
              'import_kind',
              SCALAR_IMPORT_KIND,
              tag_id=7)
      ])

  gen.AddNode(
      name='ASTModuleStatement',
      tag_id=121,
      parent='ASTStatement',
      fields=[
          Field(
              'name',
              'ASTPathExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'options_list',
              'ASTOptionsList',
              tag_id=3,
              private_comment="""
              May be NULL
              """),
      ])

  gen.AddNode(
      name='ASTWithConnectionClause',
      tag_id=122,
      parent='ASTNode',
      fields=[
          Field(
              'connection_clause',
              'ASTConnectionClause',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
      ])

  gen.AddNode(
      name='ASTIntoAlias',
      tag_id=123,
      parent='ASTNode',
      fields=[
          Field(
              'identifier',
              'ASTIdentifier',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
      ],
      extra_public_defs="""
  // Get the unquoted and unescaped string value of this alias.
  std::string GetAsString() const;
  absl::string_view GetAsStringView() const;
  IdString GetAsIdString() const;
      """)

  gen.AddNode(
      name='ASTUnnestExpressionWithOptAliasAndOffset',
      tag_id=124,
      parent='ASTNode',
      comment="""
      A conjunction of the unnest expression and the optional alias and offset.
      """,
      fields=[
          Field(
              'unnest_expression',
              'ASTUnnestExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'optional_alias',
              'ASTAlias',
              tag_id=3),
          Field(
              'optional_with_offset',
              'ASTWithOffset',
              tag_id=4)
      ])

  gen.AddNode(
      name='ASTPivotExpression',
      tag_id=125,
      parent='ASTNode',
      fields=[
          Field(
              'expression',
              'ASTExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'alias',
              'ASTAlias',
              tag_id=3)
      ])

  gen.AddNode(
      name='ASTPivotValue',
      tag_id=126,
      parent='ASTNode',
      fields=[
          Field(
              'value',
              'ASTExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'alias',
              'ASTAlias',
              tag_id=3),
      ])

  gen.AddNode(
      name='ASTPivotExpressionList',
      tag_id=127,
      parent='ASTNode',
      fields=[
          Field(
              'expressions',
              'ASTPivotExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REST_AS_REPEATED),
      ])

  gen.AddNode(
      name='ASTPivotValueList',
      tag_id=128,
      parent='ASTNode',
      fields=[
          Field(
              'values',
              'ASTPivotValue',
              tag_id=2,
              field_loader=FieldLoaderMethod.REST_AS_REPEATED),
      ])

  gen.AddNode(
      name='ASTPivotClause',
      tag_id=129,
      parent='ASTNode',
      fields=[
          Field(
              'pivot_expressions',
              'ASTPivotExpressionList',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'for_expression',
              'ASTExpression',
              tag_id=3,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'pivot_values',
              'ASTPivotValueList',
              tag_id=4,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'output_alias',
              'ASTAlias',
              tag_id=5),
      ])

  gen.AddNode(
      name='ASTUnpivotInItem',
      tag_id=130,
      parent='ASTNode',
      fields=[
          Field(
              'unpivot_columns',
              'ASTPathExpressionList',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'alias',
              'ASTUnpivotInItemLabel',
              tag_id=3),
      ])

  gen.AddNode(
      name='ASTUnpivotInItemList',
      tag_id=131,
      parent='ASTNode',
      fields=[
          Field(
              'in_items',
              'ASTUnpivotInItem',
              tag_id=2,
              field_loader=FieldLoaderMethod.REST_AS_REPEATED),
      ])

  gen.AddNode(
      name='ASTUnpivotClause',
      tag_id=132,
      parent='ASTNode',
      use_custom_debug_string=True,
      fields=[
          Field(
              'unpivot_output_value_columns',
              'ASTPathExpressionList',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'unpivot_output_name_column',
              'ASTPathExpression',
              tag_id=3,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'unpivot_in_items',
              'ASTUnpivotInItemList',
              tag_id=4,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'output_alias',
              'ASTAlias',
              tag_id=5),
          Field(
              'null_filter',
              SCALAR_NULL_FILTER,
              tag_id=6),
      ],
      extra_public_defs="""
  std::string GetSQLForNullFilter() const;
      """)

  gen.AddNode(
      name='ASTUsingClause',
      tag_id=133,
      parent='ASTNode',
      fields=[
          Field(
              'keys',
              'ASTIdentifier',
              tag_id=2,
              field_loader=FieldLoaderMethod.REST_AS_REPEATED),
      ])

  gen.AddNode(
      name='ASTForSystemTime',
      tag_id=134,
      parent='ASTNode',
      fields=[
          Field(
              'expression',
              'ASTExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
      ])

  gen.AddNode(
      name='ASTQualify',
      tag_id=135,
      parent='ASTNode',
      fields=[
          Field(
              'expression',
              'ASTExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
      ])

  gen.AddNode(
      name='ASTClampedBetweenModifier',
      tag_id=136,
      parent='ASTNode',
      fields=[
          Field(
              'low',
              'ASTExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'high',
              'ASTExpression',
              tag_id=3,
              field_loader=FieldLoaderMethod.REQUIRED),
      ])
  gen.AddNode(
      name='ASTWithReportModifier',
      tag_id=334,
      parent='ASTNode',
      fields=[
          Field(
              'options_list',
              'ASTOptionsList',
              tag_id=2,
              field_loader=FieldLoaderMethod.OPTIONAL),
      ])

  gen.AddNode(
      name='ASTFormatClause',
      tag_id=137,
      parent='ASTNode',
      fields=[
          Field(
              'format',
              'ASTExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'time_zone_expr',
              'ASTExpression',
              tag_id=3,
              field_loader=FieldLoaderMethod.OPTIONAL_EXPRESSION),
      ])

  gen.AddNode(
      name='ASTPathExpressionList',
      tag_id=138,
      parent='ASTNode',
      fields=[
          Field(
              'path_expression_list',
              'ASTPathExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REST_AS_REPEATED,
              comment="""
              Guaranteed by the parser to never be empty.
              """),
      ])

  gen.AddNode(
      name='ASTParameterExpr',
      tag_id=139,
      parent='ASTParameterExprBase',
      use_custom_debug_string=True,
      fields=[
          Field(
              'name',
              'ASTIdentifier',
              tag_id=2),
          Field(
              'position',
              SCALAR_INT,
              tag_id=3,
              private_comment="""
              1-based position of the parameter in the query. Mutually exclusive
              with name_.
              """),
      ])

  gen.AddNode(
      name='ASTSystemVariableExpr',
      tag_id=140,
      parent='ASTParameterExprBase',
      fields=[
          Field(
              'path',
              'ASTPathExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
      ])

  gen.AddNode(
      name='ASTWithGroupRows',
      tag_id=141,
      parent='ASTNode',
      fields=[
          Field(
              'subquery',
              'ASTQuery',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
      ])

  gen.AddNode(
      name='ASTLambda',
      tag_id=142,
      parent='ASTExpression',
      comment="""
      Function argument is required to be expression.
      """,
      fields=[
          Field(
              'argument_list',
              'ASTExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED,
              private_comment="""
              Empty parameter list is represented as empty
              ASTStructConstructorWithParens.
              """),
          Field(
              'body',
              'ASTExpression',
              tag_id=3,
              field_loader=FieldLoaderMethod.REQUIRED,
              private_comment="""
              Required, never NULL.
              """),
      ])

  gen.AddNode(
      name='ASTAnalyticFunctionCall',
      tag_id=143,
      parent='ASTExpression',
      fields=[
          Field(
              'expression',
              'ASTExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED,
              gen_setters_and_getters=False,
              private_comment="""
              Required, never NULL.
              The expression is has to be either an ASTFunctionCall or an
              ASTFunctionCallWithGroupRows.
              """),
          Field(
              'window_spec',
              'ASTWindowSpecification',
              tag_id=3,
              field_loader=FieldLoaderMethod.REQUIRED,
              private_comment="""
              Required, never NULL.
              """),
      ],
      extra_public_defs="""
  // Exactly one of function() or function_with_group_rows() will be non-null.
  //
  // In the normal case, function() is non-null.
  //
  // The function_with_group_rows() case can only happen if
  // FEATURE_V_1_3_WITH_GROUP_ROWS is enabled and one function call has both
  // WITH GROUP_ROWS and an OVER clause.
  const ASTFunctionCall* function() const;
  const ASTFunctionCallWithGroupRows* function_with_group_rows() const;
      """)

  gen.AddNode(
      name='ASTFunctionCallWithGroupRows',
      tag_id=144,
      parent='ASTExpression',
      fields=[
          Field(
              'function',
              'ASTFunctionCall',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED,
              private_comment="""
              Required, never NULL.
              """),
          Field(
              'subquery',
              'ASTQuery',
              tag_id=3,
              field_loader=FieldLoaderMethod.REQUIRED,
              private_comment="""
              Required, never NULL.
              """),
      ])

  gen.AddNode(
      name='ASTClusterBy',
      tag_id=145,
      parent='ASTNode',
      fields=[
          Field(
              'clustering_expressions',
              'ASTExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REST_AS_REPEATED),
      ])

  gen.AddNode(
      name='ASTNewConstructorArg',
      tag_id=146,
      parent='ASTNode',
      comment="""
 At most one of 'optional_identifier' and 'optional_path_expression' are
 set.
       """,
      fields=[
          Field(
              'expression',
              'ASTExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field('optional_identifier', 'ASTIdentifier', tag_id=3),
          Field('optional_path_expression', 'ASTPathExpression', tag_id=4),
      ])

  gen.AddNode(
      name='ASTNewConstructor',
      tag_id=147,
      parent='ASTExpression',
      fields=[
          Field(
              'type_name',
              'ASTSimpleType',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'arguments',
              'ASTNewConstructorArg',
              tag_id=3,
              field_loader=FieldLoaderMethod.REST_AS_REPEATED),
      ],
      # legacy non-standard getter
      extra_public_defs="""
  const ASTNewConstructorArg* argument(int i) const { return arguments_[i]; }
      """)

  gen.AddNode(
      name='ASTBracedConstructorFieldValue',
      tag_id=330,
      parent='ASTExpression',
      fields=[
          Field(
              'expression',
              'ASTExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
      ])

  gen.AddNode(
      name='ASTBracedConstructorField',
      tag_id=331,
      parent='ASTNode',
      comment="""Exactly one of 'identifier' and 'parenthesized_path' is
                 set.""",
      fields=[
          Field(
              'identifier',
              'ASTIdentifier',
              tag_id=2,
          ),
          Field('parenthesized_path', 'ASTPathExpression', tag_id=3),
          Field(
              'value',
              'ASTBracedConstructorFieldValue',
              tag_id=4,
              field_loader=FieldLoaderMethod.REQUIRED),
      ])

  gen.AddNode(
      name='ASTBracedConstructor',
      tag_id=332,
      parent='ASTExpression',
      fields=[
          Field(
              'fields',
              'ASTBracedConstructorField',
              tag_id=3,
              field_loader=FieldLoaderMethod.REST_AS_REPEATED),
      ])

  gen.AddNode(
      name='ASTBracedNewConstructor',
      tag_id=333,
      parent='ASTExpression',
      fields=[
          Field(
              'type_name',
              'ASTSimpleType',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'braced_constructor',
              'ASTBracedConstructor',
              tag_id=3,
              field_loader=FieldLoaderMethod.REQUIRED),
      ])

  gen.AddNode(
      name='ASTOptionsList',
      tag_id=148,
      parent='ASTNode',
      fields=[
          Field(
              'options_entries',
              'ASTOptionsEntry',
              tag_id=2,
              field_loader=FieldLoaderMethod.REST_AS_REPEATED),
      ])

  gen.AddNode(
      name='ASTOptionsEntry',
      tag_id=149,
      parent='ASTNode',
      fields=[
          Field(
              'name',
              'ASTIdentifier',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'value',
              'ASTExpression',
              tag_id=3,
              field_loader=FieldLoaderMethod.REQUIRED,
              comment="""
              Value is always an identifier, literal, or parameter.
              """),
      ])

  gen.AddNode(
      name='ASTCreateStatement',
      tag_id=150,
      parent='ASTDdlStatement',
      is_abstract=True,
      use_custom_debug_string=True,
      custom_debug_string_comment="""
      This adds the modifiers is_temp, etc, to the node name.
      """,
      comment="""
      Common superclass of CREATE statements supporting the common
      modifiers:
        CREATE [OR REPLACE] [TEMP|PUBLIC|PRIVATE] <object> [IF NOT EXISTS].
      """,
      fields=[
          Field(
              'scope',
              SCALAR_SCOPE,
              tag_id=2),
          Field(
              'is_or_replace',
              SCALAR_BOOL,
              tag_id=3),
          Field(
              'is_if_not_exists',
              SCALAR_BOOL,
              tag_id=4),
      ],
      extra_public_defs="""
  bool is_default_scope() const { return scope_ == DEFAULT_SCOPE; }
  bool is_private() const { return scope_ == PRIVATE; }
  bool is_public() const { return scope_ == PUBLIC; }
  bool is_temp() const { return scope_ == TEMPORARY; }

  bool IsCreateStatement() const override { return true; }
      """,
      extra_protected_defs="""
  virtual void CollectModifiers(std::vector<std::string>* modifiers) const;
      """)

  gen.AddNode(
      name='ASTFunctionParameter',
      tag_id=151,
      parent='ASTNode',
      use_custom_debug_string=True,
      fields=[
          Field(
              'name',
              'ASTIdentifier',
              tag_id=2),
          Field(
              'type',
              'ASTType',
              tag_id=3,
              field_loader=FieldLoaderMethod.OPTIONAL_TYPE,
              private_comment="""
              Only one of <type_>, <templated_parameter_type_>, or <tvf_schema_>
              will be set.

              This is the type for concrete scalar parameters.
              """),
          Field(
              'templated_parameter_type',
              'ASTTemplatedParameterType',
              tag_id=4,
              private_comment="""
          This indicates a templated parameter type, which may be either a
          templated scalar type (ANY PROTO, ANY STRUCT, etc.) or templated table
          type as indicated by its kind().
              """),
          Field(
              'tvf_schema',
              'ASTTVFSchema',
              tag_id=5,
              private_comment="""
              Only allowed for table-valued functions, indicating a table type
              parameter.
              """),
          Field(
              'alias',
              'ASTAlias',
              tag_id=6),
          Field(
              'default_value',
              'ASTExpression',
              tag_id=7,
              field_loader=FieldLoaderMethod.OPTIONAL_EXPRESSION,
              private_comment="""
              The default value of the function parameter if specified.
              """),
          Field(
              'procedure_parameter_mode',
              SCALAR_PROCEDURE_PARAMETER_MODE,
              tag_id=8,
              private_comment="""
         Function parameter doesn't use this field and always has value NOT_SET.
         Procedure parameter should have this field set during parsing.
              """),
          Field(
              'is_not_aggregate',
              SCALAR_BOOL,
              tag_id=9,
              private_comment="""
              True if the NOT AGGREGATE modifier is present.
              """),
      ],
      extra_public_defs="""

  bool IsTableParameter() const;
  bool IsTemplated() const {
    return templated_parameter_type_ != nullptr;
  }

  static std::string ProcedureParameterModeToString(
      ProcedureParameterMode mode);
      """)

  gen.AddNode(
      name='ASTFunctionParameters',
      tag_id=152,
      parent='ASTNode',
      fields=[
          Field(
              'parameter_entries',
              'ASTFunctionParameter',
              tag_id=2,
              field_loader=FieldLoaderMethod.REST_AS_REPEATED),
      ])

  gen.AddNode(
      name='ASTFunctionDeclaration',
      tag_id=153,
      parent='ASTNode',
      fields=[
          Field(
              'name',
              'ASTPathExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'parameters',
              'ASTFunctionParameters',
              tag_id=3,
              field_loader=FieldLoaderMethod.REQUIRED),
      ],
      extra_public_defs="""
  // Returns whether or not any of the <parameters_> are templated.
  bool IsTemplated() const;
      """)

  gen.AddNode(
      name='ASTSqlFunctionBody',
      tag_id=154,
      parent='ASTNode',
      fields=[
          Field(
              'expression',
              'ASTExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.OPTIONAL_EXPRESSION),
      ])

  gen.AddNode(
      name='ASTTVFArgument',
      tag_id=155,
      parent='ASTNode',
      comment="""
  This represents an argument to a table-valued function (TVF). ZetaSQL can
  parse the argument in one of the following ways:

  (1) ZetaSQL parses the argument as an expression; if any arguments are
      table subqueries then ZetaSQL will parse them as subquery expressions
      and the resolver may interpret them as needed later. In this case the
      expr_ of this class is filled.

  (2) ZetaSQL parses the argument as "TABLE path"; this syntax represents a
      table argument including all columns in the named table. In this case the
      table_clause_ of this class is non-empty.

  (3) ZetaSQL parses the argument as "MODEL path"; this syntax represents a
      model argument. In this case the model_clause_ of this class is
      non-empty.

  (4) ZetaSQL parses the argument as "CONNECTION path"; this syntax
      represents a connection argument. In this case the connection_clause_ of
      this class is non-empty.

  (5) ZetaSQL parses the argument as a named argument; this behaves like when
      the argument is an expression with the extra requirement that the
      resolver rearranges the provided named arguments to match the required
      argument names from the function signature, if present. The named
      argument is stored in the expr_ of this class in this case since an
      ASTNamedArgument is a subclass of ASTExpression.
  (6) ZetaSQL parses the argument as "DESCRIPTOR"; this syntax represents a
     descriptor on a list of columns with optional types.
      """,
      fields=[
          Field(
              'expr',
              'ASTExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.OPTIONAL_EXPRESSION,
              private_comment="""
              Only one of expr, table_clause, model_clause, connection_clause or
              descriptor may be non-null.
              """),
          Field(
              'table_clause',
              'ASTTableClause',
              tag_id=3),
          Field(
              'model_clause',
              'ASTModelClause',
              tag_id=4),
          Field(
              'connection_clause',
              'ASTConnectionClause',
              tag_id=5),
          Field(
              # We unfortunately cannot name this field "descriptor" because the
              # proto generates a field of that name.
              'desc',
              'ASTDescriptor',
              tag_id=6,
              gen_setters_and_getters=False),
      ],
      extra_public_defs="""
  const ASTDescriptor* descriptor() const {return desc_;}
      """)

  gen.AddNode(
      name='ASTTVF',
      tag_id=156,
      parent='ASTTableExpression',
      comment="""
    This represents a call to a table-valued function (TVF). Each TVF returns an
    entire output relation instead of a single scalar value. The enclosing query
    may refer to the TVF as if it were a table subquery. The TVF may accept
    scalar arguments and/or other input relations.
      """,
      fields=[
          Field(
              'name',
              'ASTPathExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'argument_entries',
              'ASTTVFArgument',
              tag_id=3,
              field_loader=FieldLoaderMethod.REPEATING_WHILE_IS_NODE_KIND),
          Field(
              'hint',
              'ASTHint',
              tag_id=4),
          Field(
              'alias',
              'ASTAlias',
              tag_id=5),
          Field(
              'pivot_clause',
              'ASTPivotClause',
              tag_id=6),
          Field(
              'unpivot_clause',
              'ASTUnpivotClause',
              tag_id=7),
          Field(
              'sample',
              'ASTSampleClause',
              tag_id=8),
      ])

  gen.AddNode(
      name='ASTTableClause',
      tag_id=157,
      parent='ASTNode',
      comment="""
     This represents a clause of form "TABLE <target>", where <target> is either
     a path expression representing a table name, or <target> is a TVF call.
     It is currently only supported for relation arguments to table-valued
     functions.
      """,
      fields=[
          Field(
              'table_path',
              'ASTPathExpression',
              tag_id=2,
              private_comment="""
              Exactly one of these will be non-null.
              """),
          Field(
              'tvf',
              'ASTTVF',
              tag_id=3),
      ])

  gen.AddNode(
      name='ASTModelClause',
      tag_id=158,
      parent='ASTNode',
      comment="""
    This represents a clause of form "MODEL <target>", where <target> is a model
    name.
      """,
      fields=[
          Field(
              'model_path',
              'ASTPathExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
      ])

  gen.AddNode(
      name='ASTConnectionClause',
      tag_id=159,
      parent='ASTNode',
      comment="""
     This represents a clause of form "CONNECTION <target>", where <target> is a
     connection name.
      """,
      fields=[
          Field(
              'connection_path',
              'ASTPathExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
      ])

  gen.AddNode(
      name='ASTTableDataSource',
      tag_id=160,
      parent='ASTTableExpression',
      is_abstract=True,
      fields=[
          Field(
              'path_expr',
              'ASTPathExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED,
              visibility=Visibility.PROTECTED),
          Field(
              'for_system_time',
              'ASTForSystemTime',
              tag_id=3,
              visibility=Visibility.PROTECTED),
          Field(
              'where_clause',
              'ASTWhereClause',
              tag_id=4,
              visibility=Visibility.PROTECTED),
      ])

  gen.AddNode(
      name='ASTCloneDataSource',
      tag_id=161,
      parent='ASTTableDataSource')

  gen.AddNode(
      name='ASTCopyDataSource',
      tag_id=162,
      parent='ASTTableDataSource')

  gen.AddNode(
      name='ASTCloneDataSourceList',
      tag_id=163,
      parent='ASTNode',
      fields=[
          Field(
              'data_sources',
              'ASTCloneDataSource',
              tag_id=2,
              field_loader=FieldLoaderMethod.REST_AS_REPEATED),
      ])

  gen.AddNode(
      name='ASTCloneDataStatement',
      tag_id=164,
      parent='ASTStatement',
      fields=[
          Field(
              'target_path',
              'ASTPathExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'data_source_list',
              'ASTCloneDataSourceList',
              tag_id=3,
              field_loader=FieldLoaderMethod.REQUIRED),
      ])

  gen.AddNode(
      name='ASTCreateConstantStatement',
      tag_id=165,
      parent='ASTCreateStatement',
      comment="""
      This represents a CREATE CONSTANT statement, i.e.,
      CREATE [OR REPLACE] [TEMP|TEMPORARY|PUBLIC|PRIVATE] CONSTANT
        [IF NOT EXISTS] <name_path> = <expression>;
      """,
      fields=[
          Field(
              'name',
              'ASTPathExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'expr',
              'ASTExpression',
              tag_id=3,
              field_loader=FieldLoaderMethod.REQUIRED),
      ],
      extra_public_defs="""
  const ASTPathExpression* GetDdlTarget() const override { return name_; }
      """)

  gen.AddNode(
      name='ASTCreateDatabaseStatement',
      tag_id=166,
      parent='ASTStatement',
      comment="""
      This represents a CREATE DATABASE statement, i.e.,
      CREATE DATABASE <name> [OPTIONS (name=value, ...)];
      """,
      fields=[
          Field(
              'name',
              'ASTPathExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'options_list',
              'ASTOptionsList',
              tag_id=3),
      ])

  gen.AddNode(
      name='ASTCreateProcedureStatement',
      tag_id=167,
      parent='ASTCreateStatement',
      fields=[
          Field(
              'name',
              'ASTPathExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'parameters',
              'ASTFunctionParameters',
              tag_id=3,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'options_list',
              'ASTOptionsList',
              tag_id=4),
          Field(
              'body',
              'ASTScript',
              tag_id=5,
              field_loader=FieldLoaderMethod.REQUIRED,
              comment="""
              The body of a procedure. Always consists of a single BeginEndBlock
              including the BEGIN/END keywords and text in between.
              """),
      ],
      extra_public_defs="""
  const ASTPathExpression* GetDdlTarget() const override { return name_; }
      """)

  gen.AddNode(
      name='ASTCreateSchemaStatement',
      tag_id=168,
      parent='ASTCreateStatement',
      comment="""
      This represents a CREATE SCHEMA statement, i.e.,
      CREATE SCHEMA <name> [OPTIONS (name=value, ...)];
      """,
      fields=[
          Field(
              'name',
              'ASTPathExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'collate',
              'ASTCollate',
              tag_id=3),
          Field(
              'options_list',
              'ASTOptionsList',
              tag_id=4),
      ],
      extra_public_defs="""
  const ASTPathExpression* GetDdlTarget() const override { return name_; }
      """)

  gen.AddNode(
      name='ASTTransformClause',
      tag_id=169,
      parent='ASTNode',
      fields=[
          Field(
              'select_list',
              'ASTSelectList',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
      ])

  gen.AddNode(
      name='ASTCreateModelStatement',
      tag_id=170,
      parent='ASTCreateStatement',
      fields=[
          Field(
              'name',
              'ASTPathExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'transform_clause',
              'ASTTransformClause',
              tag_id=3),
          Field(
              'options_list',
              'ASTOptionsList',
              tag_id=4),
          Field(
              'query',
              'ASTQuery',
              tag_id=5),
      ],
      extra_public_defs="""
  const ASTPathExpression* GetDdlTarget() const override { return name_; }
      """)

  gen.AddNode(
      name='ASTIndexAllColumns',
      tag_id=171,
      parent='ASTLeaf',
      comment="Represents 'ALL COLUMNS' index key expression.")

  gen.AddNode(
      name='ASTIndexItemList',
      tag_id=172,
      parent='ASTNode',
      comment="""
      Represents the list of expressions used to order an index.
      """,
      fields=[
          Field(
              'ordering_expressions',
              'ASTOrderingExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REST_AS_REPEATED),
      ])

  gen.AddNode(
      name='ASTIndexStoringExpressionList',
      tag_id=173,
      parent='ASTNode',
      comment="""
      Represents the list of expressions being used in the STORING clause of an
      index.
      """,
      fields=[
          Field(
              'expressions',
              'ASTExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REST_AS_REPEATED),
      ])
  gen.AddNode(
      name='ASTIndexUnnestExpressionList',
      tag_id=174,
      parent='ASTNode',
      comment="""
      Represents the list of unnest expressions for create_index.
      """,
      fields=[
          Field(
              'unnest_expressions',
              'ASTUnnestExpressionWithOptAliasAndOffset',
              tag_id=2,
              field_loader=FieldLoaderMethod.REST_AS_REPEATED),
      ])
  gen.AddNode(
      name='ASTCreateIndexStatement',
      tag_id=175,
      parent='ASTCreateStatement',
      use_custom_debug_string=True,
      comment="""
      Represents a CREATE INDEX statement.
      """,
      fields=[
          Field(
              'name',
              'ASTPathExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'table_name',
              'ASTPathExpression',
              tag_id=3,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'optional_table_alias',
              'ASTAlias',
              tag_id=4),
          Field(
              'optional_index_unnest_expression_list',
              'ASTIndexUnnestExpressionList',
              tag_id=5),

          Field(
              'index_item_list',
              'ASTIndexItemList',
              tag_id=6,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'optional_index_storing_expressions',
              'ASTIndexStoringExpressionList',
              tag_id=7),
          Field(
              'options_list',
              'ASTOptionsList',
              tag_id=8),
          Field(
              'is_unique',
              SCALAR_BOOL,
              tag_id=9),
          Field(
              'is_search',
              SCALAR_BOOL,
              tag_id=10),
      ],
      extra_public_defs="""
  const ASTPathExpression* GetDdlTarget() const override { return name_; }
      """
      )

  gen.AddNode(
      name='ASTExportDataStatement',
      tag_id=176,
      parent='ASTStatement',
      fields=[
          Field(
              'with_connection_clause',
              'ASTWithConnectionClause',
              tag_id=2),
          Field(
              'options_list',
              'ASTOptionsList',
              tag_id=3),
          Field(
              'query',
              'ASTQuery',
              tag_id=4,
              field_loader=FieldLoaderMethod.REQUIRED),
      ])

  gen.AddNode(
      name='ASTExportModelStatement',
      tag_id=177,
      parent='ASTStatement',
      fields=[
          Field(
              'model_name_path',
              'ASTPathExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'with_connection_clause',
              'ASTWithConnectionClause',
              tag_id=3),
          Field(
              'options_list',
              'ASTOptionsList',
              tag_id=4),
      ])

  gen.AddNode(
      name='ASTCallStatement',
      tag_id=178,
      parent='ASTStatement',
      fields=[
          Field(
              'procedure_name',
              'ASTPathExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'arguments',
              'ASTTVFArgument',
              tag_id=3,
              field_loader=FieldLoaderMethod.REST_AS_REPEATED),
      ])

  gen.AddNode(
      name='ASTDefineTableStatement',
      tag_id=179,
      parent='ASTStatement',
      fields=[
          Field(
              'name',
              'ASTPathExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'options_list',
              'ASTOptionsList',
              tag_id=3,
              field_loader=FieldLoaderMethod.REQUIRED),
      ])

  gen.AddNode(
      name='ASTWithPartitionColumnsClause',
      tag_id=180,
      parent='ASTNode',
      fields=[
          Field(
              'table_element_list',
              'ASTTableElementList',
              tag_id=2),
      ])

  gen.AddNode(
      name='ASTCreateSnapshotTableStatement',
      tag_id=181,
      parent='ASTCreateStatement',
      fields=[
          Field(
              'name',
              'ASTPathExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'clone_data_source',
              'ASTCloneDataSource',
              tag_id=3,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'options_list',
              'ASTOptionsList',
              tag_id=4),
      ],
      extra_public_defs="""
  const ASTPathExpression* GetDdlTarget() const override { return name_; }
      """)

  gen.AddNode(
      name='ASTTypeParameterList',
      tag_id=182,
      parent='ASTNode',
      fields=[
          Field(
              'parameters',
              'ASTLeaf',
              tag_id=2,
              field_loader=FieldLoaderMethod.REST_AS_REPEATED),
      ])

  gen.AddNode(
      name='ASTTVFSchema',
      tag_id=183,
      parent='ASTNode',
      comment="""
   This represents a relation argument or return type for a table-valued
   function (TVF). The resolver can convert each ASTTVFSchema directly into a
   TVFRelation object suitable for use in TVF signatures. For more information
   about the TVFRelation object, please refer to public/table_valued_function.h.
   TODO: Change the names of these objects to make them generic and
   re-usable wherever we want to represent the schema of some intermediate or
   final table. Same for ASTTVFSchemaColumn.
      """,
      fields=[
          Field(
              'columns',
              'ASTTVFSchemaColumn',
              tag_id=2,
              field_loader=FieldLoaderMethod.REST_AS_REPEATED),
      ])

  gen.AddNode(
      name='ASTTVFSchemaColumn',
      tag_id=184,
      parent='ASTNode',
      comment="""
      This represents one column of a relation argument or return value for a
      table-valued function (TVF). It contains the name and type of the column.
      """,
      fields=[
          Field(
              'name',
              'ASTIdentifier',
              tag_id=2,
              comment="""
              name_ will be NULL for value tables.
              """),
          Field(
              'type',
              'ASTType',
              tag_id=3,
              field_loader=FieldLoaderMethod.REQUIRED),
      ])

  gen.AddNode(
      name='ASTTableAndColumnInfo',
      tag_id=185,
      parent='ASTNode',
      fields=[
          Field(
              'table_name',
              'ASTPathExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'column_list',
              'ASTColumnList',
              tag_id=3),
      ])

  gen.AddNode(
      name='ASTTableAndColumnInfoList',
      tag_id=186,
      parent='ASTNode',
      fields=[
          Field(
              'table_and_column_info_entries',
              'ASTTableAndColumnInfo',
              tag_id=2,
              field_loader=FieldLoaderMethod.REST_AS_REPEATED),
      ])

  gen.AddNode(
      name='ASTTemplatedParameterType',
      tag_id=187,
      parent='ASTNode',
      fields=[
          Field(
              'kind',
              SCALAR_TEMPLATED_TYPE_KIND,
              tag_id=2),
      ])

  gen.AddNode(
      name='ASTDefaultLiteral',
      tag_id=188,
      parent='ASTExpression',
      comment="""
      This represents the value DEFAULT that shows up in DML statements.
      It will not show up as a general expression anywhere else.
      """)

  gen.AddNode(
      name='ASTAnalyzeStatement',
      tag_id=189,
      parent='ASTStatement',
      fields=[
          Field(
              'options_list',
              'ASTOptionsList',
              tag_id=2),
          Field(
              'table_and_column_info_list',
              'ASTTableAndColumnInfoList',
              tag_id=3),
      ])

  gen.AddNode(
      name='ASTAssertStatement',
      tag_id=190,
      parent='ASTStatement',
      fields=[
          Field(
              'expr',
              'ASTExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'description',
              'ASTStringLiteral',
              tag_id=3),
      ])

  gen.AddNode(
      name='ASTAssertRowsModified',
      tag_id=191,
      parent='ASTNode',
      fields=[
          Field(
              'num_rows',
              'ASTExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
      ])

  gen.AddNode(
      name='ASTReturningClause',
      tag_id=192,
      parent='ASTNode',
      comment="""
      This represents the {THEN RETURN} clause.
      (broken link)
      """,
      fields=[
          Field(
              'select_list',
              'ASTSelectList',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'action_alias',
              'ASTAlias',
              tag_id=3),
      ])

  gen.AddNode(
      name='ASTDeleteStatement',
      tag_id=193,
      parent='ASTStatement',
      comment="""
      This is used for both top-level DELETE statements and for nested DELETEs
      inside ASTUpdateItem. When used at the top-level, the target is always a
      path expression.
      """,
      fields=[
          Field(
              'target_path',
              'ASTGeneralizedPathExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field('hint', 'ASTHint', tag_id=8),
          Field(
              'alias',
              'ASTAlias',
              tag_id=3),
          Field(
              'offset',
              'ASTWithOffset',
              tag_id=4),
          Field(
              'where',
              'ASTExpression',
              tag_id=5,
              field_loader=FieldLoaderMethod.OPTIONAL_EXPRESSION),
          Field(
              'assert_rows_modified',
              'ASTAssertRowsModified',
              tag_id=6),
          Field(
              'returning',
              'ASTReturningClause',
              tag_id=7),
      ],
      extra_public_defs="""
  // Verifies that the target path is an ASTPathExpression and, if so, returns
  // it. The behavior is undefined when called on a node that represents a
  // nested DELETE.
  absl::StatusOr<const ASTPathExpression*> GetTargetPathForNonNested() const;

  const ASTGeneralizedPathExpression* GetTargetPathForNested() const {
    return target_path_;
  }
      """)

  gen.AddNode(
      name='ASTColumnAttribute',
      tag_id=194,
      parent='ASTNode',
      is_abstract=True,
      extra_public_defs="""
  virtual std::string SingleNodeSqlString() const = 0;
      """)

  gen.AddNode(
      name='ASTNotNullColumnAttribute',
      tag_id=195,
      parent='ASTColumnAttribute',
      extra_public_defs="""
  std::string SingleNodeSqlString() const override;
      """)

  gen.AddNode(
      name='ASTHiddenColumnAttribute',
      tag_id=196,
      parent='ASTColumnAttribute',
      extra_public_defs="""
  std::string SingleNodeSqlString() const override;
      """)

  gen.AddNode(
      name='ASTPrimaryKeyColumnAttribute',
      tag_id=197,
      parent='ASTColumnAttribute',
      use_custom_debug_string=True,
      fields=[
          Field(
              'enforced',
              SCALAR_BOOL_DEFAULT_TRUE,
              tag_id=2)

      ],
      extra_public_defs="""
  std::string SingleNodeSqlString() const override;
      """)

  gen.AddNode(
      name='ASTForeignKeyColumnAttribute',
      tag_id=198,
      parent='ASTColumnAttribute',
      fields=[
          Field(
              'constraint_name',
              'ASTIdentifier',
              tag_id=2),
          Field(
              'reference',
              'ASTForeignKeyReference',
              tag_id=3,
              field_loader=FieldLoaderMethod.REQUIRED),
      ],
      extra_public_defs="""
  std::string SingleNodeSqlString() const override;
      """)

  gen.AddNode(
      name='ASTColumnAttributeList',
      tag_id=199,
      parent='ASTNode',
      fields=[
          Field(
              'values',
              'ASTColumnAttribute',
              tag_id=2,
              field_loader=FieldLoaderMethod.REST_AS_REPEATED),
      ])

  gen.AddNode(
      name='ASTStructColumnField',
      tag_id=200,
      parent='ASTNode',
      fields=[
          Field(
              'name',
              'ASTIdentifier',
              tag_id=2,
              comment="""
            name_ will be NULL for anonymous fields like in STRUCT<int, string>.
              """),
          Field(
              'schema',
              'ASTColumnSchema',
              tag_id=3,
              field_loader=FieldLoaderMethod.REQUIRED),
      ])

  gen.AddNode(
      name='ASTGeneratedColumnInfo',
      tag_id=201,
      parent='ASTNode',
      use_custom_debug_string=True,
      custom_debug_string_comment="""
      Adds stored_mode (if needed) to the debug string.
      """,
      fields=[
          Field(
              'expression',
              'ASTExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'stored_mode',
              SCALAR_STORED_MODE,
              tag_id=3),
      ],
      extra_public_defs="""
  std::string GetSqlForStoredMode() const;
      """)

  gen.AddNode(
      name='ASTTableElement',
      tag_id=202,
      parent='ASTNode',
      is_abstract=True,
      comment="""
      Base class for CREATE TABLE elements, including column definitions and
      table constraints.
      """)

  gen.AddNode(
      name='ASTColumnDefinition',
      tag_id=203,
      parent='ASTTableElement',
      fields=[
          Field(
              'name',
              'ASTIdentifier',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'schema',
              'ASTColumnSchema',
              tag_id=3,
              field_loader=FieldLoaderMethod.REQUIRED),
      ])

  gen.AddNode(
      name='ASTTableElementList',
      tag_id=204,
      parent='ASTNode',
      fields=[
          Field(
              'elements',
              'ASTTableElement',
              tag_id=2,
              field_loader=FieldLoaderMethod.REST_AS_REPEATED),
      ])

  gen.AddNode(
      name='ASTColumnList',
      tag_id=205,
      parent='ASTNode',
      fields=[
          Field(
              'identifiers',
              'ASTIdentifier',
              tag_id=2,
              field_loader=FieldLoaderMethod.REST_AS_REPEATED),
      ])

  gen.AddNode(
      name='ASTColumnPosition',
      tag_id=206,
      parent='ASTNode',
      use_custom_debug_string=True,
      fields=[
          Field(
              'identifier',
              'ASTIdentifier',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'type',
              SCALAR_RELATIVE_POSITION_TYPE,
              tag_id=3),
      ])

  gen.AddNode(
      name='ASTInsertValuesRow',
      tag_id=207,
      parent='ASTNode',
      fields=[
          Field(
              'values',
              'ASTExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REST_AS_REPEATED,
              comment="""
             A row of values in a VALUES clause.  May include ASTDefaultLiteral.
              """),
      ])

  gen.AddNode(
      name='ASTInsertValuesRowList',
      tag_id=208,
      parent='ASTNode',
      fields=[
          Field(
              'rows',
              'ASTInsertValuesRow',
              tag_id=2,
              field_loader=FieldLoaderMethod.REST_AS_REPEATED),
      ])

  gen.AddNode(
      name='ASTInsertStatement',
      tag_id=209,
      parent='ASTStatement',
      use_custom_debug_string=True,
      comment="""
      This is used for both top-level INSERT statements and for nested INSERTs
      inside ASTUpdateItem. When used at the top-level, the target is always a
      path expression.
      """,
      fields=[
          Field(
              'target_path',
              'ASTGeneralizedPathExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field('hint', 'ASTHint', tag_id=10),
          Field(
              'column_list',
              'ASTColumnList',
              tag_id=3),
          Field(
              'rows',
              'ASTInsertValuesRowList',
              tag_id=4,
              comment="""
              Non-NULL rows() means we had a VALUES clause.
              This is mutually exclusive with query() and with().
              """,
              private_comment="""
              Exactly one of rows_ or query_ will be present.
              with_ can be present if query_ is present.
              """),
          Field(
              'query',
              'ASTQuery',
              tag_id=5),
          Field(
              'assert_rows_modified',
              'ASTAssertRowsModified',
              tag_id=6),
          Field(
              'returning',
              'ASTReturningClause',
              tag_id=7),
          Field(
              'parse_progress',
              SCALAR_PARSE_PROGRESS,
              tag_id=8,
              comment="""
      This is used by the Bison parser to store the latest element of the INSERT
      syntax that was seen. The INSERT statement is extremely complicated to
      parse in bison because it is very free-form, almost everything is optional
      and almost all of the keywords are also usable as identifiers. So we parse
      it in a very free-form way, and enforce the grammar in code during/after
      parsing.
              """),
          Field(
              'insert_mode',
              SCALAR_INSERT_MODE,
              tag_id=9),
      ],
      extra_public_defs="""
  const ASTGeneralizedPathExpression* GetTargetPathForNested() const {
     return target_path_;
  }

  std::string GetSQLForInsertMode() const;

  // Verifies that the target path is an ASTPathExpression and, if so, returns
  // it. The behavior is undefined when called on a node that represents a
  // nested INSERT.
  absl::StatusOr<const ASTPathExpression*> GetTargetPathForNonNested() const;
""")

  gen.AddNode(
      name='ASTUpdateSetValue',
      tag_id=210,
      parent='ASTNode',
      fields=[
          Field(
              'path',
              'ASTGeneralizedPathExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'value',
              'ASTExpression',
              tag_id=3,
              field_loader=FieldLoaderMethod.REQUIRED,
              comment="""
              The rhs of SET X=Y.  May be ASTDefaultLiteral.
              """),
      ])

  gen.AddNode(
      name='ASTUpdateItem',
      tag_id=211,
      parent='ASTNode',
      fields=[
          Field(
              'set_value',
              'ASTUpdateSetValue',
              tag_id=2,
              private_comment="""
              Exactly one of set_value, insert_statement, delete_statement
              or update_statement will be non-NULL.
              """),
          Field(
              'insert_statement',
              'ASTInsertStatement',
              tag_id=3),
          Field(
              'delete_statement',
              'ASTDeleteStatement',
              tag_id=4),
          Field(
              'update_statement',
              'ASTUpdateStatement',
              tag_id=5),
      ])

  gen.AddNode(
      name='ASTUpdateItemList',
      tag_id=212,
      parent='ASTNode',
      fields=[
          Field(
              'update_items',
              'ASTUpdateItem',
              tag_id=2,
              field_loader=FieldLoaderMethod.REST_AS_REPEATED),
      ])

  gen.AddNode(
      name='ASTUpdateStatement',
      tag_id=213,
      parent='ASTStatement',
      comment="""
      This is used for both top-level UPDATE statements and for nested UPDATEs
      inside ASTUpdateItem. When used at the top-level, the target is always a
      path expression.
      """,
      fields=[
          Field(
              'target_path',
              'ASTGeneralizedPathExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field('hint', 'ASTHint', tag_id=10),
          Field(
              'alias',
              'ASTAlias',
              tag_id=3),
          Field(
              'offset',
              'ASTWithOffset',
              tag_id=4),
          Field(
              'update_item_list',
              'ASTUpdateItemList',
              tag_id=5,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'from_clause',
              'ASTFromClause',
              tag_id=6),
          Field(
              'where',
              'ASTExpression',
              tag_id=7,
              field_loader=FieldLoaderMethod.OPTIONAL_EXPRESSION),
          Field(
              'assert_rows_modified',
              'ASTAssertRowsModified',
              tag_id=8),
          Field(
              'returning',
              'ASTReturningClause',
              tag_id=9),
      ],
      extra_public_defs="""
  const ASTGeneralizedPathExpression* GetTargetPathForNested() const {
    return target_path_;
  }

  // Verifies that the target path is an ASTPathExpression and, if so, returns
  // it. The behavior is undefined when called on a node that represents a
  // nested UPDATE.
  absl::StatusOr<const ASTPathExpression*> GetTargetPathForNonNested() const;
      """
      )
  gen.AddNode(
      name='ASTTruncateStatement',
      tag_id=214,
      parent='ASTStatement',
      fields=[
          Field(
              'target_path',
              'ASTPathExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'where',
              'ASTExpression',
              tag_id=3,
              field_loader=FieldLoaderMethod.OPTIONAL_EXPRESSION),
      ],
      extra_public_defs="""
  // Verifies that the target path is an ASTPathExpression and, if so, returns
  // it. The behavior is undefined when called on a node that represents a
  // nested TRUNCATE (but this is not allowed by the parser).
  absl::StatusOr<const ASTPathExpression*> GetTargetPathForNonNested() const;
      """)

  gen.AddNode(
      name='ASTMergeAction',
      tag_id=215,
      parent='ASTNode',
      use_custom_debug_string=True,
      fields=[
          Field(
              'insert_column_list',
              'ASTColumnList',
              tag_id=2,
              comment="""
     Exactly one of the INSERT/UPDATE/DELETE operation must be defined in
     following ways,
       -- INSERT, action_type() is INSERT. The insert_column_list() is optional.
          The insert_row() must be non-null, but may have an empty value list.
       -- UPDATE, action_type() is UPDATE. update_item_list() is non-null.
       -- DELETE, action_type() is DELETE.
              """,
              private_comment="""
              For INSERT operation.
              """),
          Field(
              'insert_row',
              'ASTInsertValuesRow',
              tag_id=3),
          Field(
              'update_item_list',
              'ASTUpdateItemList',
              tag_id=4,
              private_comment="""
              For UPDATE operation.
              """),
          Field(
              'action_type',
              SCALAR_ACTION_TYPE,
              tag_id=5,
              private_comment="""
              Merge action type.
              """),
      ])

  gen.AddNode(
      name='ASTMergeWhenClause',
      tag_id=216,
      parent='ASTNode',
      use_custom_debug_string=True,
      fields=[
          Field(
              'search_condition',
              'ASTExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.OPTIONAL_EXPRESSION),
          Field(
              'action',
              'ASTMergeAction',
              tag_id=3,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'match_type',
              SCALAR_MATCH_TYPE,
              tag_id=4),
      ],
      extra_public_defs="""
  std::string GetSQLForMatchType() const;
      """)

  gen.AddNode(
      name='ASTMergeWhenClauseList',
      tag_id=217,
      parent='ASTNode',
      fields=[
          Field(
              'clause_list',
              'ASTMergeWhenClause',
              tag_id=2,
              field_loader=FieldLoaderMethod.REST_AS_REPEATED),
      ])

  gen.AddNode(
      name='ASTMergeStatement',
      tag_id=218,
      parent='ASTStatement',
      fields=[
          Field(
              'target_path',
              'ASTPathExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'alias',
              'ASTAlias',
              tag_id=3),
          Field(
              'table_expression',
              'ASTTableExpression',
              tag_id=4,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'merge_condition',
              'ASTExpression',
              tag_id=5,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'when_clauses',
              'ASTMergeWhenClauseList',
              tag_id=6,
              field_loader=FieldLoaderMethod.REQUIRED),
      ])

  gen.AddNode(
      name='ASTPrivilege',
      tag_id=219,
      parent='ASTNode',
      fields=[
          Field(
              'privilege_action',
              'ASTIdentifier',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field('paths', 'ASTPathExpressionList', tag_id=3),
      ])

  gen.AddNode(
      name='ASTPrivileges',
      tag_id=220,
      parent='ASTNode',
      comment="""
      Represents privileges to be granted or revoked. It can be either or a
      non-empty list of ASTPrivilege, or "ALL PRIVILEGES" in which case the list
      will be empty.
      """,
      fields=[
          Field(
              'privileges',
              'ASTPrivilege',
              tag_id=2,
              field_loader=FieldLoaderMethod.REST_AS_REPEATED),
      ],
      extra_public_defs="""
  bool is_all_privileges() const {
    // Empty Span means ALL PRIVILEGES.
    return privileges_.empty();
  }
      """)

  gen.AddNode(
      name='ASTGranteeList',
      tag_id=221,
      parent='ASTNode',
      fields=[
          Field(
              'grantee_list',
              'ASTExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REST_AS_REPEATED,
              private_comment="""
              An ASTGranteeList element may either be a string literal or
              parameter.
              """),
      ])

  gen.AddNode(
      name='ASTGrantStatement',
      tag_id=222,
      parent='ASTStatement',
      fields=[
          Field(
              'privileges',
              'ASTPrivileges',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'target_type',
              'ASTIdentifier',
              tag_id=3),
          Field(
              'target_path',
              'ASTPathExpression',
              tag_id=4,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'grantee_list',
              'ASTGranteeList',
              tag_id=5,
              field_loader=FieldLoaderMethod.REQUIRED),
      ])

  gen.AddNode(
      name='ASTRevokeStatement',
      tag_id=223,
      parent='ASTStatement',
      fields=[
          Field(
              'privileges',
              'ASTPrivileges',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'target_type',
              'ASTIdentifier',
              tag_id=3),
          Field(
              'target_path',
              'ASTPathExpression',
              tag_id=4,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'grantee_list',
              'ASTGranteeList',
              tag_id=5,
              field_loader=FieldLoaderMethod.REQUIRED),
      ])

  gen.AddNode(
      name='ASTRepeatableClause',
      tag_id=224,
      parent='ASTNode',
      fields=[
          Field(
              'argument',
              'ASTExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
      ])

  gen.AddNode(
      name='ASTFilterFieldsArg',
      tag_id=225,
      parent='ASTNode',
      use_custom_debug_string=True,
      fields=[
          Field(
              'path_expression',
              'ASTGeneralizedPathExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'filter_type',
              SCALAR_FILTER_TYPE,
              tag_id=3),
      ],
      extra_public_defs="""
  std::string GetSQLForOperator() const;
      """)

  gen.AddNode(
      name='ASTReplaceFieldsArg',
      tag_id=227,
      parent='ASTNode',
      fields=[
          Field(
              'expression',
              'ASTExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'path_expression',
              'ASTGeneralizedPathExpression',
              tag_id=3,
              field_loader=FieldLoaderMethod.REQUIRED),
      ])

  gen.AddNode(
      name='ASTReplaceFieldsExpression',
      tag_id=228,
      parent='ASTExpression',
      fields=[
          Field(
              'expr',
              'ASTExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'arguments',
              'ASTReplaceFieldsArg',
              tag_id=3,
              field_loader=FieldLoaderMethod.REST_AS_REPEATED),
      ])

  gen.AddNode(
      name='ASTSampleSize',
      tag_id=229,
      parent='ASTNode',
      fields=[
          Field(
              'size',
              'ASTExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'partition_by',
              'ASTPartitionBy',
              tag_id=3,
              private_comment="""
              Can only be non-NULL when 'unit_' is parser::ROWS.
              """),
          Field(
              'unit',
              SCALAR_UNIT,
              tag_id=4,
              comment="""
              Returns the token kind corresponding to the sample-size unit, i.e.
              parser::ROWS or parser::PERCENT.
              """),
      ],
      extra_public_defs="""
  // Returns the SQL keyword for the sample-size unit, i.e. "ROWS" or "PERCENT".
  std::string GetSQLForUnit() const;

      """)

  gen.AddNode(
      name='ASTWithWeight',
      tag_id=230,
      parent='ASTNode',
      fields=[
          Field(
              'alias',
              'ASTAlias',
              tag_id=2,
              comment="""
              alias may be NULL.
              """,
              ),
      ])

  gen.AddNode(
      name='ASTSampleSuffix',
      tag_id=231,
      parent='ASTNode',
      fields=[
          Field(
              'weight',
              'ASTWithWeight',
              tag_id=2,
              comment="""
              weight and repeat may be NULL.
              """),
          Field(
              'repeat',
              'ASTRepeatableClause',
              tag_id=3),
      ])

  gen.AddNode(
      name='ASTSampleClause',
      tag_id=232,
      parent='ASTNode',
      fields=[
          Field(
              'sample_method',
              'ASTIdentifier',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'sample_size',
              'ASTSampleSize',
              tag_id=3,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'sample_suffix',
              'ASTSampleSuffix',
              tag_id=4),
      ])

  gen.AddNode(
      name='ASTAlterAction',
      tag_id=233,
      parent='ASTNode',
      is_abstract=True,
      comment="""
      Common parent for all actions in ALTER statements
      """,
      extra_public_defs="""
  virtual std::string GetSQLForAlterAction() const = 0;
      """)

  gen.AddNode(
      name='ASTSetOptionsAction',
      tag_id=234,
      parent='ASTAlterAction',
      comment="""
      ALTER action for "SET OPTIONS ()" clause
      """,
      fields=[
          Field(
              'options_list',
              'ASTOptionsList',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
      ],
      extra_public_defs="""
  std::string GetSQLForAlterAction() const override;
      """)

  gen.AddNode(
      name='ASTSetAsAction',
      tag_id=235,
      parent='ASTAlterAction',
      comment="""
      ALTER action for "SET AS" clause
      """,
      fields=[
          Field(
              'json_body',
              'ASTJSONLiteral',
              tag_id=2),
          Field(
              'text_body',
              'ASTStringLiteral',
              tag_id=3),
      ],
      extra_public_defs="""
  std::string GetSQLForAlterAction() const override;
      """)

  gen.AddNode(
      name='ASTAddConstraintAction',
      tag_id=236,
      parent='ASTAlterAction',
      use_custom_debug_string=True,
      comment="""
      ALTER table action for "ADD CONSTRAINT" clause
      """,
      fields=[
          Field(
              'constraint',
              'ASTTableConstraint',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'is_if_not_exists',
              SCALAR_BOOL,
              tag_id=3),
      ],
      extra_public_defs="""
  std::string GetSQLForAlterAction() const override;
      """)

  gen.AddNode(
      name='ASTDropPrimaryKeyAction',
      tag_id=237,
      parent='ASTAlterAction',
      use_custom_debug_string=True,
      comment="""
      ALTER table action for "DROP PRIMARY KEY" clause
      """,
      fields=[
          Field(
              'is_if_exists',
              SCALAR_BOOL,
              tag_id=2),
      ],
      extra_public_defs="""
  std::string GetSQLForAlterAction() const override;
      """)

  gen.AddNode(
      name='ASTDropConstraintAction',
      tag_id=238,
      parent='ASTAlterAction',
      use_custom_debug_string=True,
      comment="""
      ALTER table action for "DROP CONSTRAINT" clause
      """,
      fields=[
          Field(
              'constraint_name',
              'ASTIdentifier',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'is_if_exists',
              SCALAR_BOOL,
              tag_id=3),
      ],
      extra_public_defs="""
  std::string GetSQLForAlterAction() const override;
      """)

  gen.AddNode(
      name='ASTAlterConstraintEnforcementAction',
      tag_id=239,
      parent='ASTAlterAction',
      use_custom_debug_string=True,
      comment="""
      ALTER table action for "ALTER CONSTRAINT identifier [NOT] ENFORCED" clause
      """,
      fields=[
          Field(
              'constraint_name',
              'ASTIdentifier',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'is_if_exists',
              SCALAR_BOOL,
              tag_id=3),
          Field(
              'is_enforced',
              SCALAR_BOOL_DEFAULT_TRUE,
              tag_id=4),
      ],
      extra_public_defs="""
  std::string GetSQLForAlterAction() const override;
      """)

  gen.AddNode(
      name='ASTAlterConstraintSetOptionsAction',
      tag_id=240,
      parent='ASTAlterAction',
      use_custom_debug_string=True,
      comment="""
      ALTER table action for "ALTER CONSTRAINT identifier SET OPTIONS" clause
      """,
      fields=[
          Field(
              'constraint_name',
              'ASTIdentifier',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'options_list',
              'ASTOptionsList',
              tag_id=3,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'is_if_exists',
              SCALAR_BOOL,
              tag_id=4),
      ],
      extra_public_defs="""
  std::string GetSQLForAlterAction() const override;
      """)

  gen.AddNode(
      name='ASTAddColumnAction',
      tag_id=241,
      parent='ASTAlterAction',
      use_custom_debug_string=True,
      comment="""
      ALTER table action for "ADD COLUMN" clause
      """,
      fields=[
          Field(
              'column_definition',
              'ASTColumnDefinition',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'column_position',
              'ASTColumnPosition',
              tag_id=3,
              comment="""
              Optional children.
              """),
          Field(
              'fill_expression',
              'ASTExpression',
              tag_id=4,
              field_loader=FieldLoaderMethod.OPTIONAL_EXPRESSION),
          Field(
              'is_if_not_exists',
              SCALAR_BOOL,
              tag_id=5),
      ],
      extra_public_defs="""
  std::string GetSQLForAlterAction() const override;
      """)

  gen.AddNode(
      name='ASTDropColumnAction',
      tag_id=242,
      parent='ASTAlterAction',
      use_custom_debug_string=True,
      comment="""
      ALTER table action for "DROP COLUMN" clause
      """,
      fields=[
          Field(
              'column_name',
              'ASTIdentifier',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'is_if_exists',
              SCALAR_BOOL,
              tag_id=3),
      ],
      extra_public_defs="""
  std::string GetSQLForAlterAction() const override;
      """)

  gen.AddNode(
      name='ASTRenameColumnAction',
      tag_id=243,
      parent='ASTAlterAction',
      use_custom_debug_string=True,
      comment="""
      ALTER table action for "RENAME COLUMN" clause
      """,
      fields=[
          Field(
              'column_name',
              'ASTIdentifier',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'new_column_name',
              'ASTIdentifier',
              tag_id=3,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'is_if_exists',
              SCALAR_BOOL,
              tag_id=4),
      ],
      extra_public_defs="""
  std::string GetSQLForAlterAction() const override;
      """)

  gen.AddNode(
      name='ASTAlterColumnTypeAction',
      tag_id=244,
      parent='ASTAlterAction',
      use_custom_debug_string=True,
      comment="""
      ALTER table action for "ALTER COLUMN SET TYPE" clause
      """,
      fields=[
          Field(
              'column_name',
              'ASTIdentifier',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'schema',
              'ASTColumnSchema',
              tag_id=3,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'collate',
              'ASTCollate',
              tag_id=4),
          Field(
              'is_if_exists',
              SCALAR_BOOL,
              tag_id=5),
      ],
      extra_public_defs="""
  std::string GetSQLForAlterAction() const override;
      """)

  gen.AddNode(
      name='ASTAlterColumnOptionsAction',
      tag_id=245,
      parent='ASTAlterAction',
      use_custom_debug_string=True,
      comment="""
      ALTER table action for "ALTER COLUMN SET OPTIONS" clause
      """,
      fields=[
          Field(
              'column_name',
              'ASTIdentifier',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'options_list',
              'ASTOptionsList',
              tag_id=3,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'is_if_exists',
              SCALAR_BOOL,
              tag_id=4),
      ],
      extra_public_defs="""
  std::string GetSQLForAlterAction() const override;
      """)

  gen.AddNode(
      name='ASTAlterColumnSetDefaultAction',
      tag_id=322,
      parent='ASTAlterAction',
      use_custom_debug_string=True,
      comment="""
      ALTER table action for "ALTER COLUMN SET DEFAULT" clause
      """,
      fields=[
          Field(
              'column_name',
              'ASTIdentifier',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'default_expression',
              'ASTExpression',
              tag_id=3,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field('is_if_exists', SCALAR_BOOL, tag_id=4),
      ],
      extra_public_defs="""
  std::string GetSQLForAlterAction() const override;
      """)

  gen.AddNode(
      name='ASTAlterColumnDropDefaultAction',
      tag_id=323,
      parent='ASTAlterAction',
      use_custom_debug_string=True,
      comment="""
      ALTER table action for "ALTER COLUMN DROP DEFAULT" clause
      """,
      fields=[
          Field(
              'column_name',
              'ASTIdentifier',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field('is_if_exists', SCALAR_BOOL, tag_id=3),
      ],
      extra_public_defs="""
  std::string GetSQLForAlterAction() const override;
      """)

  gen.AddNode(
      name='ASTAlterColumnDropNotNullAction',
      tag_id=246,
      parent='ASTAlterAction',
      use_custom_debug_string=True,
      comment="""
      ALTER table action for "ALTER COLUMN DROP NOT NULL" clause
      """,
      fields=[
          Field(
              'column_name',
              'ASTIdentifier',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'is_if_exists',
              SCALAR_BOOL,
              tag_id=3),
      ],
      extra_public_defs="""
  std::string GetSQLForAlterAction() const override;
      """)

  gen.AddNode(
      name='ASTGrantToClause',
      tag_id=247,
      parent='ASTAlterAction',
      comment="""
      ALTER ROW ACCESS POLICY action for "GRANT TO (<grantee_list>)" or "TO
      <grantee_list>" clause, also used by CREATE ROW ACCESS POLICY
      """,
      fields=[
          Field(
              'grantee_list',
              'ASTGranteeList',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'has_grant_keyword_and_parens',
              SCALAR_BOOL,
              tag_id=3),
      ],
      extra_public_defs="""
  std::string GetSQLForAlterAction() const override;
      """)

  gen.AddNode(
      name='ASTRestrictToClause',
      tag_id=327,
      parent='ASTAlterAction',
      comment="""
      ALTER PRIVILEGE RESTRICTION action for "RESTRICT TO (<restrictee_list>)"
      clause, also used by CREATE PRIVILEGE RESTRICTION
      """,
      fields=[
          Field(
              'restrictee_list',
              'ASTGranteeList',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
      ],
      extra_public_defs="""
  std::string GetSQLForAlterAction() const override;
      """)

  gen.AddNode(
      name='ASTAddToRestricteeListClause',
      tag_id=328,
      parent='ASTAlterAction',
      comment="""
      ALTER PRIVILEGE RESTRICTION action for "ADD (<restrictee_list>)" clause
      """,
      fields=[
          Field('is_if_not_exists', SCALAR_BOOL, tag_id=2),
          Field(
              'restrictee_list',
              'ASTGranteeList',
              tag_id=3,
              field_loader=FieldLoaderMethod.REQUIRED),
      ],
      extra_public_defs="""
  std::string GetSQLForAlterAction() const override;
      """)

  gen.AddNode(
      name='ASTRemoveFromRestricteeListClause',
      tag_id=329,
      parent='ASTAlterAction',
      comment="""
      ALTER PRIVILEGE RESTRICTION action for "REMOVE (<restrictee_list>)" clause
      """,
      fields=[
          Field('is_if_exists', SCALAR_BOOL, tag_id=2),
          Field(
              'restrictee_list',
              'ASTGranteeList',
              tag_id=3,
              field_loader=FieldLoaderMethod.REQUIRED),
      ],
      extra_public_defs="""
  std::string GetSQLForAlterAction() const override;
      """)

  gen.AddNode(
      name='ASTFilterUsingClause',
      tag_id=248,
      parent='ASTAlterAction',
      comment="""
      ALTER ROW ACCESS POLICY action for "[FILTER] USING (<expression>)" clause,
      also used by CREATE ROW ACCESS POLICY
      """,
      fields=[
          Field(
              'predicate',
              'ASTExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'has_filter_keyword',
              SCALAR_BOOL,
              tag_id=3),
      ],
      extra_public_defs="""
  std::string GetSQLForAlterAction() const override;
      """)

  gen.AddNode(
      name='ASTRevokeFromClause',
      tag_id=249,
      parent='ASTAlterAction',
      use_custom_debug_string=True,
      comment="""
    ALTER ROW ACCESS POLICY action for "REVOKE FROM (<grantee_list>)|ALL" clause
      """,
      fields=[
          Field(
              'revoke_from_list',
              'ASTGranteeList',
              tag_id=2),
          Field(
              'is_revoke_from_all',
              SCALAR_BOOL,
              tag_id=3),
      ],
      extra_public_defs="""
  std::string GetSQLForAlterAction() const override;
      """)

  gen.AddNode(
      name='ASTRenameToClause',
      tag_id=250,
      parent='ASTAlterAction',
      comment="""
      ALTER ROW ACCESS POLICY action for "RENAME TO <new_name>" clause,
      and ALTER table action for "RENAME TO" clause.
      """,
      fields=[
          Field(
              'new_name',
              'ASTPathExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
      ],
      extra_public_defs="""
  std::string GetSQLForAlterAction() const override;
      """)

  gen.AddNode(
      name='ASTSetCollateClause',
      tag_id=251,
      parent='ASTAlterAction',
      comment="""
      ALTER action for "SET COLLATE ()" clause
      """,
      fields=[
          Field(
              'collate',
              'ASTCollate',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
      ],
      extra_public_defs="""
  std::string GetSQLForAlterAction() const override;
      """)

  gen.AddNode(
      name='ASTAlterSubEntityAction',
      tag_id=330,
      parent='ASTAlterAction',
      comment="""
      ALTER action for "ALTER <subentity>" clause
      """,
      fields=[
          Field(
              'type',
              'ASTIdentifier',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'name',
              'ASTIdentifier',
              tag_id=3,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'action',
              'ASTAlterAction',
              tag_id=4,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field('is_if_exists', SCALAR_BOOL, tag_id=5),
      ],
      extra_public_defs="""
  std::string GetSQLForAlterAction() const override;
  std::string SingleNodeDebugString() const override;
      """)

  gen.AddNode(
      name='ASTAddSubEntityAction',
      tag_id=331,
      parent='ASTAlterAction',
      comment="""
      ALTER action for "ADD <subentity>" clause
      """,
      fields=[
          Field(
              'type',
              'ASTIdentifier',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'name',
              'ASTIdentifier',
              tag_id=3,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field('options_list', 'ASTOptionsList', tag_id=4),
          Field('is_if_not_exists', SCALAR_BOOL, tag_id=5),
      ],
      extra_public_defs="""
  std::string GetSQLForAlterAction() const override;
  std::string SingleNodeDebugString() const override;
      """)

  gen.AddNode(
      name='ASTDropSubEntityAction',
      tag_id=332,
      parent='ASTAlterAction',
      comment="""
      ALTER action for "DROP <subentity>" clause
      """,
      fields=[
          Field(
              'type',
              'ASTIdentifier',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'name',
              'ASTIdentifier',
              tag_id=3,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field('is_if_exists', SCALAR_BOOL, tag_id=5),
      ],
      extra_public_defs="""
  std::string GetSQLForAlterAction() const override;
  std::string SingleNodeDebugString() const override;
      """)

  gen.AddNode(
      name='ASTAlterActionList',
      tag_id=252,
      parent='ASTNode',
      fields=[
          Field(
              'actions',
              'ASTAlterAction',
              tag_id=2,
              field_loader=FieldLoaderMethod.REST_AS_REPEATED),
      ])

  gen.AddNode(
      name='ASTAlterAllRowAccessPoliciesStatement',
      tag_id=253,
      parent='ASTStatement',
      fields=[
          Field(
              'table_name_path',
              'ASTPathExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'alter_action',
              'ASTAlterAction',
              tag_id=3,
              field_loader=FieldLoaderMethod.REQUIRED),
      ])

  gen.AddNode(
      name='ASTForeignKeyActions',
      tag_id=254,
      parent='ASTNode',
      use_custom_debug_string=True,
      fields=[
          Field(
              'update_action',
              SCALAR_ACTION,
              tag_id=2),
          Field(
              'delete_action',
              SCALAR_ACTION,
              tag_id=3),
      ],
      extra_public_defs="""
  static std::string GetSQLForAction(Action action);
      """)

  gen.AddNode(
      name='ASTForeignKeyReference',
      tag_id=255,
      parent='ASTNode',
      use_custom_debug_string=True,
      fields=[
          Field(
              'table_name',
              'ASTPathExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'column_list',
              'ASTColumnList',
              tag_id=3,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'actions',
              'ASTForeignKeyActions',
              tag_id=4,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'match',
              SCALAR_MATCH,
              tag_id=5),
          Field(
              'enforced',
              SCALAR_BOOL_DEFAULT_TRUE,
              tag_id=6),
      ],
      extra_public_defs="""
  std::string GetSQLForMatch() const;
      """)

  gen.AddNode(
      name='ASTScript',
      tag_id=256,
      parent='ASTNode',
      comment="""
      A top-level script.
      """,
      fields=[
          Field(
              'statement_list_node',
              'ASTStatementList',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
      ],
      extra_public_defs="""
  absl::Span<const ASTStatement* const> statement_list() const {
    return statement_list_node_->statement_list();
  }
      """)

  gen.AddNode(
      name='ASTElseifClause',
      tag_id=257,
      parent='ASTNode',
      comment="""
      Represents an ELSEIF clause in an IF statement.
      """,
      fields=[
          Field(
              'condition',
              'ASTExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED,
              comment="""
              condition and body are both required.
              """),
          Field(
              'body',
              'ASTStatementList',
              tag_id=3,
              field_loader=FieldLoaderMethod.REQUIRED),
      ],
      extra_public_defs="""
  // Returns the ASTIfStatement that this ASTElseifClause belongs to.
  const ASTIfStatement* if_stmt() const {
    return parent()->parent()->GetAsOrDie<ASTIfStatement>();
  }
      """)

  gen.AddNode(
      name='ASTElseifClauseList',
      tag_id=258,
      parent='ASTNode',
      comment="""
      Represents a list of ELSEIF clauses.  Note that this list is never empty,
      as the grammar will not create an ASTElseifClauseList object unless there
      exists at least one ELSEIF clause.
      """,
      fields=[
          Field(
              'elseif_clauses',
              'ASTElseifClause',
              tag_id=2,
              field_loader=FieldLoaderMethod.REST_AS_REPEATED),
      ])

  gen.AddNode(
      name='ASTIfStatement',
      tag_id=259,
      parent='ASTScriptStatement',
      fields=[
          Field(
              'condition',
              'ASTExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED,
              comment="""
              condition and then_list are both required.
              """),
          Field(
              'then_list',
              'ASTStatementList',
              tag_id=3,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'elseif_clauses',
              'ASTElseifClauseList',
              tag_id=4,
              comment="""
          Optional; nullptr if no ELSEIF clauses are specified.  If present, the
          list will never be empty.
              """),
          Field(
              'else_list',
              'ASTStatementList',
              tag_id=5,
              comment="""
              Optional; nullptr if no ELSE clause is specified
              """),
      ])

  gen.AddNode(
      name='ASTWhenThenClause',
      tag_id=260,
      parent='ASTNode',
      comment="""
      Represents a WHEN...THEN clause in a CASE statement.
      """,
      fields=[
          Field(
              'condition',
              'ASTExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED,
              comment="""
              condition and body are both required.
              """),
          Field(
              'body',
              'ASTStatementList',
              tag_id=3,
              field_loader=FieldLoaderMethod.REQUIRED),
      ],
      extra_public_defs="""
  // Returns the ASTCaseStatement that this ASTWhenThenClause belongs to.
  // Immediate parent is an ASTWhenThenClauseList, contained in an
  // ASTCaseStatement.
  const ASTCaseStatement* case_stmt() const {
    return parent()->parent()->GetAsOrDie<ASTCaseStatement>();
  }
      """)

  gen.AddNode(
      name='ASTWhenThenClauseList',
      tag_id=261,
      parent='ASTNode',
      comment="""
   Represents a list of WHEN...THEN clauses. Note that this list is never empty,
   as the grammar mandates that there is at least one WHEN...THEN clause in
   a CASE statement.
      """,
      fields=[
          Field(
              'when_then_clauses',
              'ASTWhenThenClause',
              tag_id=2,
              field_loader=FieldLoaderMethod.REST_AS_REPEATED),
      ])

  gen.AddNode(
      name='ASTCaseStatement',
      tag_id=262,
      parent='ASTScriptStatement',
      fields=[
          Field(
              'expression',
              'ASTExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.OPTIONAL_EXPRESSION,
              comment="""
              Optional; nullptr if not specified
              """),
          Field(
              'when_then_clauses',
              'ASTWhenThenClauseList',
              tag_id=3,
              field_loader=FieldLoaderMethod.REQUIRED,
              comment="""
              Required field.
              """),
          Field(
              'else_list',
              'ASTStatementList',
              tag_id=4),
      ])

  gen.AddNode(
      name='ASTHint',
      tag_id=263,
      parent='ASTNode',
      fields=[
          Field(
              'num_shards_hint',
              'ASTIntLiteral',
              tag_id=2,
              comment="""
      This is the @num_shards hint shorthand that can occur anywhere that a
      hint can occur, prior to @{...} hints.
      At least one of num_shards_hints is non-NULL or hint_entries is non-empty.
              """),
          Field(
              'hint_entries',
              'ASTHintEntry',
              tag_id=3,
              field_loader=FieldLoaderMethod.REST_AS_REPEATED),
      ])

  gen.AddNode(
      name='ASTHintEntry',
      tag_id=264,
      parent='ASTNode',
      fields=[
          Field(
              'qualifier',
              'ASTIdentifier',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'name',
              'ASTIdentifier',
              tag_id=3,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'value',
              'ASTExpression',
              tag_id=4,
              field_loader=FieldLoaderMethod.REQUIRED,
              comment="""
              Value is always an identifier, literal, or parameter.
              """),
      ],
      gen_init_fields=False,
      extra_private_defs="""
  absl::Status InitFields() final {
    // We need a special case here because we have two children that both have
    // type ASTIdentifier and the first one is optional.
    if (num_children() == 2) {
      FieldLoader fl(this);
      ZETASQL_RETURN_IF_ERROR(fl.AddRequired(&name_));
      ZETASQL_RETURN_IF_ERROR(fl.AddRequired(&value_));
      return fl.Finalize();
    } else {
      FieldLoader fl(this);
      ZETASQL_RETURN_IF_ERROR(fl.AddRequired(&qualifier_));
      ZETASQL_RETURN_IF_ERROR(fl.AddRequired(&name_));
      ZETASQL_RETURN_IF_ERROR(fl.AddRequired(&value_));
      return fl.Finalize();
    }
  }
      """)

  gen.AddNode(
      name='ASTUnpivotInItemLabel',
      tag_id=265,
      parent='ASTNode',
      fields=[
          Field(
              'string_label',
              'ASTStringLiteral',
              tag_id=2,
              gen_setters_and_getters=False),
          Field(
              'int_label',
              'ASTIntLiteral',
              tag_id=3,
              gen_setters_and_getters=False),
      ],
      extra_public_defs="""
  const ASTLeaf* label() const {
    if (string_label_ != nullptr) {
      return string_label_;
    }
    return int_label_;
  }
      """)

  gen.AddNode(
      name='ASTDescriptor',
      tag_id=266,
      parent='ASTNode',
      fields=[
          Field(
              'columns',
              'ASTDescriptorColumnList',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
      ])

  gen.AddNode(
      name='ASTColumnSchema',
      tag_id=267,
      parent='ASTNode',
      is_abstract=True,
      comment="""
      A column schema identifies the column type and the column annotations.
      The annotations consist of the column attributes and the column options.

      This class is used only in column definitions of CREATE TABLE statements,
      and is unrelated to CREATE SCHEMA despite the usage of the overloaded term
      "schema".

      The hierarchy of column schema is similar to the type hierarchy.
      The annotations can be applied on struct fields or array elements, for
      example, as in STRUCT<x INT64 NOT NULL, y STRING OPTIONS(foo="bar")>.
      In this case, some column attributes, such as PRIMARY KEY and HIDDEN, are
      disallowed as field attributes.
      """,
      fields=[
          Field(
              'type_parameters',
              'ASTTypeParameterList',
              tag_id=2,
              visibility=Visibility.PROTECTED),
          Field(
              'generated_column_info',
              'ASTGeneratedColumnInfo',
              tag_id=3,
              visibility=Visibility.PROTECTED),
          Field(
              'default_expression',
              'ASTExpression',
              tag_id=4,
              field_loader=FieldLoaderMethod.OPTIONAL_EXPRESSION,
              visibility=Visibility.PROTECTED),
          Field(
              'collate',
              'ASTCollate',
              tag_id=5,
              visibility=Visibility.PROTECTED),
          Field(
              'attributes',
              'ASTColumnAttributeList',
              tag_id=6,
              visibility=Visibility.PROTECTED),
          Field(
              'options_list',
              'ASTOptionsList',
              tag_id=7,
              visibility=Visibility.PROTECTED),
      ],
      extra_public_defs="""
  // Helper method that returns true if the attributes()->values() contains an
  // ASTColumnAttribute with the node->kind() equal to 'node_kind'.
  bool ContainsAttribute(ASTNodeKind node_kind) const;

  template <typename T>
  std::vector<const T*> FindAttributes(ASTNodeKind node_kind) const {
    std::vector<const T*> found;
    if (attributes() == nullptr) {
      return found;
    }
    for (const ASTColumnAttribute* attribute : attributes()->values()) {
      if (attribute->node_kind() == node_kind) {
        found.push_back(static_cast<const T*>(attribute));
      }
    }
    return found;
  }
      """)

  gen.AddNode(
      name='ASTSimpleColumnSchema',
      tag_id=268,
      parent='ASTColumnSchema',
      fields=[
          Field(
              'type_name',
              'ASTPathExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
      ])

  gen.AddNode(
      name='ASTArrayColumnSchema',
      tag_id=269,
      parent='ASTColumnSchema',
      fields=[
          Field(
              'element_schema',
              'ASTColumnSchema',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
      ])

  gen.AddNode(
      name='ASTTableConstraint',
      tag_id=270,
      parent='ASTTableElement',
      is_abstract=True,
      comment="""
      Base class for constraints, including primary key, foreign key and check
      constraints.
      """,
      extra_public_defs="""
  virtual const ASTIdentifier* constraint_name() const = 0;
      """)

  gen.AddNode(
      name='ASTPrimaryKey',
      tag_id=271,
      parent='ASTTableConstraint',
      use_custom_debug_string=True,
      fields=[
          Field(
              'column_list',
              'ASTColumnList',
              tag_id=2),
          Field(
              'options_list',
              'ASTOptionsList',
              tag_id=3),
          Field(
              'constraint_name',
              'ASTIdentifier',
              tag_id=4,
              getter_is_override=True),
          Field(
              'enforced',
              SCALAR_BOOL_DEFAULT_TRUE,
              tag_id=5),
      ])

  gen.AddNode(
      name='ASTForeignKey',
      tag_id=272,
      parent='ASTTableConstraint',
      fields=[
          Field(
              'column_list',
              'ASTColumnList',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'reference',
              'ASTForeignKeyReference',
              tag_id=3,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'options_list',
              'ASTOptionsList',
              tag_id=4),
          Field(
              'constraint_name',
              'ASTIdentifier',
              tag_id=5,
              getter_is_override=True),
      ])

  gen.AddNode(
      name='ASTCheckConstraint',
      tag_id=273,
      parent='ASTTableConstraint',
      use_custom_debug_string=True,
      fields=[
          Field(
              'expression',
              'ASTExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'options_list',
              'ASTOptionsList',
              tag_id=3),
          Field(
              'constraint_name',
              'ASTIdentifier',
              tag_id=4,
              getter_is_override=True),
          Field(
              'is_enforced',
              SCALAR_BOOL_DEFAULT_TRUE,
              tag_id=5),
      ])

  gen.AddNode(
      name='ASTDescriptorColumn',
      tag_id=274,
      parent='ASTNode',
      fields=[
          Field(
              'name',
              'ASTIdentifier',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED,
              comment="""
              Required field
              """),
      ])

  gen.AddNode(
      name='ASTDescriptorColumnList',
      tag_id=275,
      parent='ASTNode',
      fields=[
          Field(
              'descriptor_column_list',
              'ASTDescriptorColumn',
              tag_id=2,
              field_loader=FieldLoaderMethod.REST_AS_REPEATED,
              comment="""
              Guaranteed by the parser to never be empty.
              """),
      ])

  gen.AddNode(
      name='ASTCreateEntityStatement',
      tag_id=276,
      parent='ASTCreateStatement',
      fields=[
          Field(
              'type',
              'ASTIdentifier',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'name',
              'ASTPathExpression',
              tag_id=3,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'options_list',
              'ASTOptionsList',
              tag_id=4),
          Field(
              'json_body',
              'ASTJSONLiteral',
              tag_id=5),
          Field(
              'text_body',
              'ASTStringLiteral',
              tag_id=6),
      ],
      extra_public_defs="""
  const ASTPathExpression* GetDdlTarget() const override { return name_; }
      """)

  gen.AddNode(
      name='ASTRaiseStatement',
      tag_id=277,
      parent='ASTScriptStatement',
      fields=[
          Field(
              'message',
              'ASTExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.OPTIONAL_EXPRESSION),
      ],
      extra_public_defs="""
  // A RAISE statement rethrows an existing exception, as opposed to creating
  // a new exception, when none of the properties are set.  Currently, the only
  // property is the message.  However, for future proofing, as more properties
  // get added to RAISE later, code should call this function to check for a
  // rethrow, rather than checking for the presence of a message, directly.
  bool is_rethrow() const { return message_ == nullptr; }
      """)

  gen.AddNode(
      name='ASTExceptionHandler',
      tag_id=278,
      parent='ASTNode',
      fields=[
          Field(
              'statement_list',
              'ASTStatementList',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED,
              comment="""
     Required field; even an empty block still contains an empty statement list.
              """),
      ])

  gen.AddNode(
      name='ASTExceptionHandlerList',
      tag_id=279,
      parent='ASTNode',
      comment="""
     Represents a list of exception handlers in a block.  Currently restricted
     to one element, but may contain multiple elements in the future, once there
     are multiple error codes for a block to catch.
      """,
      fields=[
          Field(
              'exception_handler_list',
              'ASTExceptionHandler',
              tag_id=2,
              field_loader=FieldLoaderMethod.REST_AS_REPEATED),
      ])

  gen.AddNode(
      name='ASTBeginEndBlock',
      tag_id=280,
      parent='ASTScriptStatement',
      fields=[
          Field('label', 'ASTLabel', tag_id=2),
          Field(
              'statement_list_node',
              'ASTStatementList',
              tag_id=3,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'handler_list',
              'ASTExceptionHandlerList',
              tag_id=4,
              comment="""
          Optional; nullptr indicates a BEGIN block without an EXCEPTION clause.
              """),
      ],
      extra_public_defs="""
  absl::Span<const ASTStatement* const> statement_list() const {
    return statement_list_node_->statement_list();
  }

  bool has_exception_handler() const {
    return handler_list_ != nullptr &&
           !handler_list_->exception_handler_list().empty();
  }
      """)

  gen.AddNode(
      name='ASTIdentifierList',
      tag_id=281,
      parent='ASTNode',
      fields=[
          Field(
              'identifier_list',
              'ASTIdentifier',
              tag_id=2,
              field_loader=FieldLoaderMethod.REST_AS_REPEATED,
              comment="""
              Guaranteed by the parser to never be empty.
              """),
      ])
  gen.AddNode(
      name='ASTVariableDeclaration',
      tag_id=282,
      parent='ASTScriptStatement',
      fields=[
          Field(
              'variable_list',
              'ASTIdentifierList',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED,
              comment="""
              Required fields
              """),
          Field(
              'type',
              'ASTType',
              tag_id=3,
              field_loader=FieldLoaderMethod.OPTIONAL_TYPE,
              comment="""
             Optional fields; at least one of <type> and <default_value> must be
             present.
              """),
          Field(
              'default_value',
              'ASTExpression',
              tag_id=4,
              field_loader=FieldLoaderMethod.OPTIONAL_EXPRESSION),
      ])

  gen.AddNode(
      name='ASTUntilClause',
      tag_id=283,
      parent='ASTNode',
      comment="""
      Represents UNTIL in a REPEAT statement.
      """,
      fields=[
          Field(
              'condition',
              'ASTExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED,
              comment="""
              Required field
              """),
      ],
      extra_public_defs="""
  // Returns the ASTRepeatStatement that this ASTUntilClause belongs to.
  const ASTRepeatStatement* repeat_stmt() const {
    return parent()->GetAsOrDie<ASTRepeatStatement>();
  }
      """)

  gen.AddNode(
      name='ASTBreakContinueStatement',
      tag_id=284,
      parent='ASTScriptStatement',
      is_abstract=True,
      comment="""
      Base class shared by break and continue statements.
      """,
      fields=[
          Field('label', 'ASTLabel', tag_id=2, visibility=Visibility.PROTECTED),
      ],
      extra_public_defs="""
  virtual void set_keyword(BreakContinueKeyword keyword) = 0;
  virtual BreakContinueKeyword keyword() const = 0;

  // Returns text representing the keyword used for this BREAK/CONINUE
  // statement.  All letters are in uppercase.
  absl::string_view GetKeywordText() const {
    switch (keyword()) {
      case BREAK:
        return "BREAK";
      case LEAVE:
        return "LEAVE";
      case CONTINUE:
        return "CONTINUE";
      case ITERATE:
        return "ITERATE";
    }
  }
      """)

  gen.AddNode(
      name='ASTBreakStatement',
      tag_id=285,
      parent='ASTBreakContinueStatement',
      fields=[
          Field(
              'keyword',
              SCALAR_BREAK_CONTINUE_KEYWORD_DEFAULT_BREAK,
              tag_id=2,
              getter_is_override=True),
      ])

  gen.AddNode(
      name='ASTContinueStatement',
      tag_id=286,
      parent='ASTBreakContinueStatement',
      fields=[
          Field(
              'keyword',
              SCALAR_BREAK_CONTINUE_KEYWORD_DEFAULT_CONTINUE,
              tag_id=2,
              getter_is_override=True),
      ])

  gen.AddNode(
      name='ASTDropPrivilegeRestrictionStatement',
      tag_id=326,
      parent='ASTDdlStatement',
      fields=[
          Field('is_if_exists', SCALAR_BOOL, tag_id=2),
          Field(
              'privileges',
              'ASTPrivileges',
              tag_id=3,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'object_type',
              'ASTIdentifier',
              tag_id=4,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'name_path',
              'ASTPathExpression',
              tag_id=5,
              field_loader=FieldLoaderMethod.REQUIRED),
      ],
      extra_public_defs="""const ASTPathExpression*
          GetDdlTarget() const override { return name_path_; }
      """)

  gen.AddNode(
      name='ASTDropRowAccessPolicyStatement',
      tag_id=287,
      parent='ASTDdlStatement',
      use_custom_debug_string=True,
      custom_debug_string_comment="""
      This adds the "if exists" modifier to the node name.
      """,
      comment="""
      Represents a DROP ROW ACCESS POLICY statement.
      """,
      fields=[
          Field(
              'name',
              'ASTPathExpression',
              tag_id=2,
              gen_setters_and_getters=False,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'table_name',
              'ASTPathExpression',
              tag_id=3,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'is_if_exists',
              SCALAR_BOOL,
              tag_id=4),
      ],
      extra_public_defs="""
  const ASTPathExpression* GetDdlTarget() const override { return name_; }

  const ASTIdentifier* name() const {
    ZETASQL_DCHECK(name_ == nullptr || name_->num_names() == 1);
    return name_ == nullptr ? nullptr : name_->name(0);
  }
      """)

  gen.AddNode(
      name='ASTCreatePrivilegeRestrictionStatement',
      tag_id=324,
      parent='ASTCreateStatement',
      fields=[
          Field(
              'privileges',
              'ASTPrivileges',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'object_type',
              'ASTIdentifier',
              tag_id=3,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'name_path',
              'ASTPathExpression',
              tag_id=4,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field('restrict_to', 'ASTRestrictToClause', tag_id=5),
      ],
      extra_public_defs="""
  const ASTPathExpression* GetDdlTarget() const override { return name_path_; }
      """)

  gen.AddNode(
      name='ASTCreateRowAccessPolicyStatement',
      tag_id=288,
      parent='ASTCreateStatement',
      fields=[
          Field(
              'target_path',
              'ASTPathExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'grant_to',
              'ASTGrantToClause',
              tag_id=3),
          Field(
              'filter_using',
              'ASTFilterUsingClause',
              tag_id=4,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'name',
              'ASTPathExpression',
              tag_id=5,
              gen_setters_and_getters=False),
          Field(
              'has_access_keyword',
              SCALAR_BOOL,
              tag_id=6),
      ],
      extra_public_defs="""
  const ASTIdentifier* name() const {
    ZETASQL_DCHECK(name_ == nullptr || name_->num_names() == 1);
    return name_ == nullptr ? nullptr : name_->name(0);
  }

  const ASTPathExpression* GetDdlTarget() const override { return name_; }
      """)

  gen.AddNode(
      name='ASTDropStatement',
      tag_id=289,
      parent='ASTDdlStatement',
      use_custom_debug_string=True,
      custom_debug_string_comment="""
      This adds the "if exists" modifier to the node name.
      """,
      comment="""
      Represents a DROP statement.
      """,
      fields=[
          Field(
              'name',
              'ASTPathExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'drop_mode',
              SCALAR_DROP_MODE,
              tag_id=3),
          Field(
              'is_if_exists',
              SCALAR_BOOL,
              tag_id=4),
          Field(
              'schema_object_kind',
              SCALAR_SCHEMA_OBJECT_KIND,
              tag_id=5),
      ],
      extra_public_defs="""
  const ASTPathExpression* GetDdlTarget() const override { return name_; }

  static std::string GetSQLForDropMode(DropMode drop_mode);
      """)

  gen.AddNode(
      name='ASTReturnStatement',
      tag_id=290,
      parent='ASTScriptStatement')

  gen.AddNode(
      name='ASTSingleAssignment',
      tag_id=291,
      parent='ASTScriptStatement',
      comment="""
      A statement which assigns to a single variable from an expression.
      Example:
        SET x = 3;
      """,
      fields=[
          Field(
              'variable',
              'ASTIdentifier',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'expression',
              'ASTExpression',
              tag_id=3,
              field_loader=FieldLoaderMethod.REQUIRED),
      ])

  gen.AddNode(
      name='ASTParameterAssignment',
      tag_id=292,
      parent='ASTStatement',
      comment="""
      A statement which assigns to a query parameter from an expression.
      Example:
        SET @x = 3;
      """,
      fields=[
          Field(
              'parameter',
              'ASTParameterExpr',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'expression',
              'ASTExpression',
              tag_id=3,
              field_loader=FieldLoaderMethod.REQUIRED),
      ])

  gen.AddNode(
      name='ASTSystemVariableAssignment',
      tag_id=293,
      parent='ASTStatement',
      comment="""
      A statement which assigns to a system variable from an expression.
      Example:
        SET @@x = 3;
      """,
      fields=[
          Field(
              'system_variable',
              'ASTSystemVariableExpr',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'expression',
              'ASTExpression',
              tag_id=3,
              field_loader=FieldLoaderMethod.REQUIRED),
      ])

  gen.AddNode(
      name='ASTAssignmentFromStruct',
      tag_id=294,
      parent='ASTScriptStatement',
      comment="""
      A statement which assigns multiple variables to fields in a struct,
      which each variable assigned to one field.
      Example:
        SET (x, y) = (5, 10);
      """,
      fields=[
          Field(
              'variables',
              'ASTIdentifierList',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'struct_expression',
              'ASTExpression',
              tag_id=3,
              field_loader=FieldLoaderMethod.REQUIRED),
      ])

  gen.AddNode(
      name='ASTCreateTableStmtBase',
      tag_id=295,
      parent='ASTCreateStatement',
      is_abstract=True,
      fields=[
          Field(
              'name',
              'ASTPathExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED,
              visibility=Visibility.PROTECTED),
          Field(
              'table_element_list',
              'ASTTableElementList',
              tag_id=3,
              visibility=Visibility.PROTECTED),
          Field(
              'options_list',
              'ASTOptionsList',
              tag_id=4,
              visibility=Visibility.PROTECTED),
          Field(
              'like_table_name',
              'ASTPathExpression',
              tag_id=5,
              visibility=Visibility.PROTECTED),
          Field(
              'collate',
              'ASTCollate',
              tag_id=6,
              visibility=Visibility.PROTECTED),
      ],
      extra_public_defs="""
  const ASTPathExpression* GetDdlTarget() const override { return name_; }
      """)

  gen.AddNode(
      name='ASTCreateTableStatement',
      tag_id=296,
      parent='ASTCreateTableStmtBase',
      fields=[
          Field(
              'clone_data_source',
              'ASTCloneDataSource',
              tag_id=2),
          Field(
              'copy_data_source',
              'ASTCopyDataSource',
              tag_id=3),
          Field(
              'partition_by',
              'ASTPartitionBy',
              tag_id=4),
          Field(
              'cluster_by',
              'ASTClusterBy',
              tag_id=5),
          Field(
              'query',
              'ASTQuery',
              tag_id=6),
      ],
      init_fields_order=[
          'name',
          'table_element_list',
          'like_table_name',
          'clone_data_source',
          'copy_data_source',
          'collate',
          'partition_by',
          'cluster_by',
          'options_list',
          'query',
      ])

  gen.AddNode(
      name='ASTCreateExternalTableStatement',
      tag_id=297,
      parent='ASTCreateTableStmtBase',
      fields=[
          Field(
              'with_partition_columns_clause',
              'ASTWithPartitionColumnsClause',
              tag_id=2),
          Field(
              'with_connection_clause',
              'ASTWithConnectionClause',
              tag_id=3),
      ],
      init_fields_order=[
          'name',
          'table_element_list',
          'like_table_name',
          'collate',
          'with_partition_columns_clause',
          'with_connection_clause',
          'options_list',
      ])

  gen.AddNode(
      name='ASTCreateViewStatementBase',
      tag_id=298,
      parent='ASTCreateStatement',
      is_abstract=True,
      fields=[
          Field(
              'name',
              'ASTPathExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED,
              visibility=Visibility.PROTECTED),
          Field(
              'column_list',
              'ASTColumnList',
              tag_id=3,
              visibility=Visibility.PROTECTED),
          Field(
              'options_list',
              'ASTOptionsList',
              tag_id=4,
              visibility=Visibility.PROTECTED),
          Field(
              'query',
              'ASTQuery',
              tag_id=5,
              field_loader=FieldLoaderMethod.REQUIRED,
              visibility=Visibility.PROTECTED),
          Field(
              'sql_security',
              SCALAR_SQL_SECURITY,
              tag_id=6,
              visibility=Visibility.PROTECTED),
          Field(
              'recursive',
              SCALAR_BOOL,
              tag_id=7,
              visibility=Visibility.PROTECTED),
      ],
      extra_protected_defs="""
  void CollectModifiers(std::vector<std::string>* modifiers) const override;
      """,
      extra_public_defs="""
  std::string GetSqlForSqlSecurity() const;

  const ASTPathExpression* GetDdlTarget() const override { return name_; }
      """)

  gen.AddNode(
      name='ASTCreateViewStatement',
      tag_id=299,
      parent='ASTCreateViewStatementBase',
      init_fields_order=[
          'name',
          'column_list',
          'options_list',
          'query',
      ])

  gen.AddNode(
      name='ASTCreateMaterializedViewStatement',
      tag_id=300,
      parent='ASTCreateViewStatementBase',
      fields=[
          Field(
              'partition_by',
              'ASTPartitionBy',
              tag_id=2),
          Field(
              'cluster_by',
              'ASTClusterBy',
              tag_id=3),
      ],
      init_fields_order=[
          'name',
          'column_list',
          'partition_by',
          'cluster_by',
          'options_list',
          'query',
      ])

  gen.AddNode(
      name='ASTLoopStatement',
      tag_id=301,
      parent='ASTScriptStatement',
      is_abstract=True,
      comment="""
      Base class for all loop statements (loop/end loop, while, foreach, etc.).
      Every loop has a body.
      """,
      fields=[
          Field(
              'label',
              'ASTLabel',
              tag_id=2,
              visibility=Visibility.PROTECTED,
              comment="""
              Optional field
              """),
          Field(
              'body',
              'ASTStatementList',
              tag_id=3,
              field_loader=FieldLoaderMethod.REQUIRED,
              visibility=Visibility.PROTECTED,
              comment="""
              Required field
              """),
      ],
      extra_public_defs="""
  bool IsLoopStatement() const override { return true; }
      """)

  gen.AddNode(
      name='ASTWhileStatement',
      tag_id=302,
      parent='ASTLoopStatement',
      comment="""
      Represents either:
        - LOOP...END LOOP (if condition is nullptr).  This is semantically
                         equivalent to WHILE(true)...END WHILE.
        - WHILE...END WHILE (if condition is not nullptr)
      """,
      fields=[
          Field(
              'condition',
              'ASTExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.OPTIONAL_EXPRESSION,
              comment="""
              The <condition> is optional.  A null <condition> indicates a
              LOOP...END LOOP construct.
              """),
      ],
      init_fields_order=[
          'label',
          'condition',
          'body',
      ])

  gen.AddNode(
      name='ASTRepeatStatement',
      tag_id=303,
      parent='ASTLoopStatement',
      comment="""
      Represents the statement REPEAT...UNTIL...END REPEAT.
      This is conceptually also called do-while.
      """,
      fields=[
          Field(
              'until_clause',
              'ASTUntilClause',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED,
              comment="""
              Required field.
              """),
      ],
      init_fields_order=[
          'label',
          'body',
          'until_clause',
      ])

  gen.AddNode(
      name='ASTForInStatement',
      tag_id=304,
      parent='ASTLoopStatement',
      comment="""
      Represents the statement FOR...IN...DO...END FOR.
      This is conceptually also called for-each.
      """,
      fields=[
          Field(
              'variable',
              'ASTIdentifier',
              field_loader=FieldLoaderMethod.REQUIRED,
              tag_id=2),
          Field(
              'query',
              'ASTQuery',
              field_loader=FieldLoaderMethod.REQUIRED,
              tag_id=3),
      ],
      init_fields_order=[
          'label',
          'variable',
          'query',
          'body',
      ])

  gen.AddNode(
      name='ASTAlterStatementBase',
      tag_id=305,
      parent='ASTDdlStatement',
      is_abstract=True,
      use_custom_debug_string=True,
      custom_debug_string_comment="""
      This adds the "if exists" modifier to the node name.
      """,
      comment="""
      Common parent class for ALTER statement, e.g., ALTER TABLE/ALTER VIEW
      """,
      fields=[
          Field(
              'path',
              'ASTPathExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.OPTIONAL,
              visibility=Visibility.PROTECTED),
          Field(
              'action_list',
              'ASTAlterActionList',
              tag_id=3,
              field_loader=FieldLoaderMethod.REQUIRED,
              visibility=Visibility.PROTECTED),
          Field(
              'is_if_exists',
              SCALAR_BOOL,
              tag_id=4),
      ],
      extra_public_defs="""
  const ASTPathExpression* GetDdlTarget() const override { return path_; }
  bool IsAlterStatement() const override { return true; }
      """)

  gen.AddNode(
      name='ASTAlterDatabaseStatement',
      tag_id=306,
      parent='ASTAlterStatementBase')

  gen.AddNode(
      name='ASTAlterSchemaStatement',
      tag_id=307,
      parent='ASTAlterStatementBase')

  gen.AddNode(
      name='ASTAlterTableStatement',
      tag_id=308,
      parent='ASTAlterStatementBase')

  gen.AddNode(
      name='ASTAlterViewStatement',
      tag_id=309,
      parent='ASTAlterStatementBase')

  gen.AddNode(
      name='ASTAlterMaterializedViewStatement',
      tag_id=310,
      parent='ASTAlterStatementBase')

  gen.AddNode(
      name='ASTAlterModelStatement',
      tag_id=336,
      parent='ASTAlterStatementBase')

  gen.AddNode(
      name='ASTAlterPrivilegeRestrictionStatement',
      tag_id=325,
      parent='ASTAlterStatementBase',
      fields=[
          Field(
              'privileges',
              'ASTPrivileges',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED,
              comment="""
              Required field.
              """),
          Field(
              'object_type',
              'ASTIdentifier',
              tag_id=3,
              field_loader=FieldLoaderMethod.REQUIRED,
              comment="""
              Required field.
              """),
      ])

  gen.AddNode(
      name='ASTAlterRowAccessPolicyStatement',
      tag_id=311,
      parent='ASTAlterStatementBase',
      fields=[
          Field(
              'name',
              'ASTIdentifier',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED,
              comment="""
              Required field.
              """),
      ])

  gen.AddNode(
      name='ASTAlterEntityStatement',
      tag_id=312,
      parent='ASTAlterStatementBase',
      fields=[
          Field(
              'type',
              'ASTIdentifier',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
      ])

  gen.AddNode(
      name='ASTCreateFunctionStmtBase',
      tag_id=313,
      parent='ASTCreateStatement',
      is_abstract=True,
      use_custom_debug_string=True,
      comment="""
      This is the common superclass of CREATE FUNCTION and CREATE TABLE FUNCTION
      statements. It contains all fields shared between the two types of
      statements, including the function declaration, return type, OPTIONS list,
      and string body (if present).
      """,
      fields=[
          Field(
              'function_declaration',
              'ASTFunctionDeclaration',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED,
              visibility=Visibility.PROTECTED),
          Field(
              'language',
              'ASTIdentifier',
              tag_id=3,
              visibility=Visibility.PROTECTED),
          Field(
              'code',
              'ASTStringLiteral',
              tag_id=4,
              visibility=Visibility.PROTECTED),
          Field(
              'options_list',
              'ASTOptionsList',
              tag_id=5,
              visibility=Visibility.PROTECTED),
          Field(
              'determinism_level',
              SCALAR_DETERMINISM_LEVEL,
              tag_id=6),
          Field(
              'sql_security',
              SCALAR_SQL_SECURITY,
              tag_id=7),
      ],
      extra_public_defs="""
  std::string GetSqlForSqlSecurity() const;
  std::string GetSqlForDeterminismLevel() const;

  const ASTPathExpression* GetDdlTarget() const override {
    return function_declaration()->name();
  }
      """)

  gen.AddNode(
      name='ASTCreateFunctionStatement',
      tag_id=314,
      parent='ASTCreateFunctionStmtBase',
      use_custom_debug_string=True,
      comment="""
   This may represent an "external language" function (e.g., implemented in a
   non-SQL programming language such as JavaScript), a "sql" function, or a
   "remote" function (e.g., implemented in a remote service and with an agnostic
   programming language).
   Note that some combinations of field setting can represent functions that are
   not actually valid due to optional members that would be inappropriate for
   one type of function or another; validity of the parsed function must be
   checked by the analyzer.
      """,
      fields=[
          Field(
              'return_type',
              'ASTType',
              field_loader=FieldLoaderMethod.OPTIONAL_TYPE,
              tag_id=2),
          Field(
              'sql_function_body',
              'ASTSqlFunctionBody',
              tag_id=3,
              private_comment="""
              For SQL functions.
              """),
          Field(
              'is_aggregate',
              SCALAR_BOOL,
              tag_id=4),
          Field(
              'is_remote',
              SCALAR_BOOL,
              tag_id=5),
          Field(
              'with_connection_clause',
              'ASTWithConnectionClause',
              tag_id=6),
      ],
      init_fields_order=[
          'function_declaration',
          'return_type',
          'language',
          'with_connection_clause',
          'code',
          'sql_function_body',
          'options_list',
      ])

  gen.AddNode(
      name='ASTCreateTableFunctionStatement',
      tag_id=315,
      parent='ASTCreateFunctionStmtBase',
      use_custom_debug_string=True,
      comment="""
   This represents a table-valued function declaration statement in ZetaSQL,
   using the CREATE TABLE FUNCTION syntax. Note that some combinations of field
   settings can represent functions that are not actually valid, since optional
   members may be inappropriate for one type of function or another; validity of
   the parsed function must be checked by the analyzer.
      """,
      fields=[
          Field(
              'return_tvf_schema',
              'ASTTVFSchema',
              tag_id=2),
          Field(
              'query',
              'ASTQuery',
              tag_id=3),
      ],
      init_fields_order=[
          'function_declaration',
          'return_tvf_schema',
          'options_list',
          'language',
          'code',
          'query',
      ])

  gen.AddNode(
      name='ASTStructColumnSchema',
      tag_id=316,
      parent='ASTColumnSchema',
      fields=[
          Field(
              'struct_fields',
              'ASTStructColumnField',
              tag_id=2,
              field_loader=FieldLoaderMethod.REPEATING_WHILE_IS_NODE_KIND),
      ])

  gen.AddNode(
      name='ASTInferredTypeColumnSchema',
      tag_id=317,
      parent='ASTColumnSchema')

  gen.AddNode(
      name='ASTExecuteIntoClause',
      tag_id=318,
      parent='ASTNode',
      fields=[
          Field(
              'identifiers',
              'ASTIdentifierList',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
      ])

  gen.AddNode(
      name='ASTExecuteUsingArgument',
      tag_id=319,
      parent='ASTNode',
      fields=[
          Field(
              'expression',
              'ASTExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'alias',
              'ASTAlias',
              tag_id=3,
              comment="""
        Optional. Absent if this argument is positional. Present if it is named.
              """),
      ])

  gen.AddNode(
      name='ASTExecuteUsingClause',
      tag_id=320,
      parent='ASTNode',
      fields=[
          Field(
              'arguments',
              'ASTExecuteUsingArgument',
              tag_id=2,
              field_loader=FieldLoaderMethod.REST_AS_REPEATED),
      ])

  gen.AddNode(
      name='ASTExecuteImmediateStatement',
      tag_id=321,
      parent='ASTStatement',
      fields=[
          Field(
              'sql',
              'ASTExpression',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'into_clause',
              'ASTExecuteIntoClause',
              tag_id=3),
          Field(
              'using_clause',
              'ASTExecuteUsingClause',
              tag_id=4),
      ])

  gen.AddNode(
      name='ASTAuxLoadDataFromFilesOptionsList',
      tag_id=322,
      parent='ASTNode',
      fields=[
          Field(
              'options_list',
              'ASTOptionsList',
              tag_id=2),
      ])

  gen.AddNode(
      name='ASTAuxLoadDataStatement',
      tag_id=323,
      parent='ASTCreateTableStmtBase',
      comment="""
    Auxiliary statement used by some engines but not formally part of the
    ZetaSQL language.
      """,
      fields=[
          Field(
              'insertion_mode',
              SCALAR_LOAD_INSERTION_MODE,
              tag_id=2),
          Field(
              'partition_by',
              'ASTPartitionBy',
              tag_id=3),
          Field(
              'cluster_by',
              'ASTClusterBy',
              tag_id=4),
          Field(
              'from_files',
              'ASTAuxLoadDataFromFilesOptionsList',
              field_loader=FieldLoaderMethod.REQUIRED,
              tag_id=5),
          Field(
              'with_partition_columns_clause',
              'ASTWithPartitionColumnsClause',
              tag_id=6),
          Field(
              'with_connection_clause',
              'ASTWithConnectionClause',
              tag_id=7),
      ],
      init_fields_order=[
          'name',
          'table_element_list',
          'collate',
          'partition_by',
          'cluster_by',
          'options_list',
          'from_files',
          'with_partition_columns_clause',
          'with_connection_clause',
      ])

  gen.AddNode(
      name='ASTLabel',
      tag_id=324,
      parent='ASTNode',
      fields=[
          Field(
              'name',
              'ASTIdentifier',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
      ])

  gen.AddNode(
      name='ASTWithExpression',
      tag_id=335,
      parent='ASTExpression',
      fields=[
          Field(
              'variables',
              'ASTSelectList',
              tag_id=2,
              field_loader=FieldLoaderMethod.REQUIRED),
          Field(
              'expression',
              'ASTExpression',
              tag_id=3,
              field_loader=FieldLoaderMethod.REQUIRED),
      ])

  gen.Generate(output_path, template_path=template_path)


if __name__ == '__main__':
  app.run(main)
