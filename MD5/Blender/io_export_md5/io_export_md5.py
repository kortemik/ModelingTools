# ***** BEGIN GPL LICENSE BLOCK ***** 
# 
# This program is free software; you can redistribute it and/or 
# modify it under the terms of the GNU General Public License 
# as published by the Free Software Foundation; either version 2 
# of the License, or (at your option) any later version. 
# 
# This program is distributed in the hope that it will be useful, 
# but WITHOUT ANY WARRANTY; without even the implied warranty of 
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the 
# GNU General Public License for more details. 
# 
# You should have received a copy of the GNU General Public License 
# along with this program; if not, write to the Free Software Foundation, 
# Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA. 
# 
# ***** END GPL LICENCE BLOCK *****
#

import struct,math,os,time,sys

import mathutils
import bpy
from bpy.props import StringProperty,EnumProperty,FloatProperty
from bpy_extras.io_utils import ExportHelper

import getopt
import traceback

#"""
#Name: 'Quake Model 5 (.md5)...'
#Blender: 263
#Group: 'Export'
#Tooltip: 'Export a Quake Model 5 File'
#
#credit to der_ton for the 2.4x Blender export script
#"""

bl_info = { # changed from bl_addon_info in 2.57 -mikshaw
    "name": "Export MD5 format (.md5mesh, .md5anim)",
    "author": "OpenTechEngine",
    "version": (1,0,0),
    "blender": (2, 6, 3),
    "api": 31847,
    "location": "File > Export > Skeletal Mesh/Animation Data (.md5mesh/.md5anim)",
    "description": "Exports MD5 Format (.md5mesh, .md5anim)",
    "warning": "See source code for list of authors",
    "wiki_url": "http://wiki.blender.org/index.php/Extensions:2.5/Py/"\
        "Scripts/File_I-O/idTech4_md5",
    "tracker_url": "https://github.com/OpenTechEngine/ModelingTools",
    "category": "Import-Export"}

''' credits to community:
der_ton, original Blender 2.4 version
Paul Zirkle aka Keless, Blender 2.5 port
motorsep, Blender 2.62 port
kat, tests and community site
mikshaw, Sauerbraten support
MCampagnini
ivar

links:
http://wiki.blender.org/index.php/Extensions:2.5/Py/Scripts/File_I-O/idTech4_md5
http://www.katsbits.com/smforum/index.php?topic=167.0
'''

class Typewriter(object):
  def print_info(message):
    print ("INFO: "+message)

  def print_warn(message):
    print ("WARNING: "+message)

  def print_error(message):
    print ("ERROR: "+message)

  info = print_info
  warn = print_warn
  error = print_error

#MATH UTILTY

class MD5Math(object):
  def getminmax(listofpoints):
    if len(listofpoints[0]) == 0:
        return ([0,0,0],[0,0,0])
    min = [listofpoints[0][0], listofpoints[1][0], listofpoints[2][0]]
    max = [listofpoints[0][0], listofpoints[1][0], listofpoints[2][0]]
    if len(listofpoints[0])>1:
      for i in range(1, len(listofpoints[0])):
        if listofpoints[i][0]>max[0]: max[0]=listofpoints[i][0]
        if listofpoints[i][1]>max[1]: max[1]=listofpoints[i][1]
        if listofpoints[i][2]>max[2]: max[2]=listofpoints[i][2]
        if listofpoints[i][0]<min[0]: min[0]=listofpoints[i][0]
        if listofpoints[i][1]<min[1]: min[1]=listofpoints[i][1]
        if listofpoints[i][2]<min[2]: min[2]=listofpoints[i][2]
    return (min, max)

################################################################################
#
# MD5File object, should be it's own module but that and blender don't cope
# http://tfc.duke.free.fr/coding/md5-specs-en.html
#

class MD5Format(object):
  def __init__(self, commandline):
    self._version = 10 # MD5 File version, hardcoded
    self._commandline = commandline  # commandline used to generate file

class MD5MeshFormat(MD5Format):
  class Joints(object):
    class _Joint(object):
      # "name" parent ( pos.x pos.y pos.z ) ( orient.x orient.y orient.z )
      def __init__(self, name, parent, pos_x, pos_y, pos_z, ori_x, ori_y, ori_z):
        self._name = name
        self._parent = parent
        self._pos_x = pos_x
        self._pos_y = pos_y
        self._pos_z = pos_z
        self._ori_x = ori_x
        self._ori_y = ori_y
        self._ori_z = ori_z

      def __str__(self):
        return "\t\"%s\" %s ( %f %f %f ) ( %f %f %f )\n" % \
          (self._name, self._parent, self._pos_x, self._pos_y, self._pos_z, self._ori_x, self._ori_y, self._ori_z)

    def __init__(self):
      self._joints = [] # list of joints

    def __len__(self):
      return len(self._joints)

    def __str__(self):
      return "joints {\n%s}\n\n" % \
        ("".join( [ str(element) for element in self._joints ] ))
    
    def Joint(self, name, parent, pos_x, pos_y, pos_z, ori_x, ori_y, ori_z):
      created_joint = self._Joint(name, parent, pos_x, pos_y, pos_z, ori_x, ori_y, ori_z)
      self._joints.append(created_joint)
      return created_joint

  class _Mesh(object):

    class _Vert(object):
      # vert vertIndex ( s t ) startWeight countWeight
      def __init__(self, index, texture_x, texture_y, weightstart, weightcount):
        self._index = index
        self._texture_x = texture_x # u, s
        self._texture_y = texture_y # v, t
        self._weightstart = weightstart
        self._weightcount = weightcount

      def __str__(self):
        return "\tvert %i ( %f %f ) %i %i\n" % \
          (self._index, self._texture_x, self._texture_y, self._weightstart, self._weightcount)


    class _Tri(object):
      # tri triIndex vertIndex[0] vertIndex[1] vertIndex[2]
      def __init__(self, index, vert1, vert2, vert3):
        self._index = index
        self._vert1 = vert1
        self._vert2 = vert2
        self._vert3 = vert3
        
      def __str__(self):
        return "\ttri %i %i %i %i\n" % \
          (self._index, self._vert1, self._vert2, self._vert3)


    class _Weight(object):
      # weight weightIndex joint bias ( pos.x pos.y pos.z )
      def __init__(self, index, joint, bias, pos_x, pos_y, pos_z):
        self._index = index
        self._rel_joint = joint
        self._bias = bias
        self._pos_x = pos_x
        self._pos_y = pos_y
        self._pos_z = pos_z

      def __str__(self):
        return "\tweight %i %i %f ( %f %f %f )\n" % \
          (self._index, self._rel_joint, self._bias, self._pos_x, self._pos_y, self._pos_z)


    def __init__(self, shader):
      self._shader = shader
      self._verts = [] # list of verts
      self._tris = [] # list of tris
      self._weights = [] # list of weights

    def __str__(self):
      return "mesh {\n\tshader \"%s\"\n\n\tnumverts %i\n%s\n\tnumtris %i\n%s\n\tnumweights %i\n%s}\n" % \
        (self._shader,
         len(self._verts),
         "".join( [ str(element) for element in self._verts ] ),
         len(self._tris),
         "".join( [ str(element) for element in self._tris ] ),
         len(self._weights),
         "".join( [ str(element) for element in self._weights ] ))


    def Vert(self, index, texture_x, texture_y, weightstart, weightcount):
      created_vert = self._Vert(index, texture_x, texture_y, weightstart, weightcount)
      self._verts.append(created_vert)
      return created_vert

    def Tri(self, index, vert1, vert2, vert3):
      created_tri = self._Tri(index, vert1, vert2, vert3)
      self._tris.append(created_tri)
      return created_tri

    def Weight(self, index, joint, bias, pos_x, pos_y, pos_z):
      created_weight = self._Weight(index, joint, bias, pos_x, pos_y, pos_z)
      self._weights.append(created_weight)
      return created_weight

  def Mesh(self, shader):
    created_mesh = self._Mesh(shader)
    self._meshes.append(created_mesh)
    return created_mesh

  def __init__(self, commandline):
    super().__init__(commandline)
    self.Joints = self.Joints() # joints
    self._meshes = [] # list of meshes

  def __str__(self):
    return "MD5Version %i\ncommandline \"%s\"\n\nnumJoints %i\nnumMeshes %i\n\n%s%s" % \
      (self._version, self._commandline, len(self.Joints), len(self._meshes), \
       str(self.Joints), \
       "".join( [ str(element) for element in self._meshes ] ))

class MD5AnimFormat(MD5Format):
  class Hierarchy(object):
    class _Joint(object):
      # name parent flags startIndex
      def __init__(self, name, parent, flags, startindex):
        self._name = name
        self._parent = parent
        self._flags = flags
        self._startindex = startindex
        
      def __str__(self):
        return "\t\"%s\" %s %i %i\n" % \
          (self._name, self._parent, self._flags, self._startindex)
        
    def __init__(self):
      self._joints = [] # joint hierarchy

    def __str__(self):
      return "hierarchy {\n%s}\n" % \
        ("".join( [ str(element) for element in self._joints ] ))

    def __len__(self):
      return len(self._joints)

    def Joint(self, name, parent, flags, startindex):
      created_joint = self._Joint(name, parent, flags, startindex)
      self._joints.append(created_joint)
      return created_joint

      
  class Bounds(object):
    class _Bound(object):
      # ( min.x min.y min.z ) ( max.x max.y max.z )
      def __init__(self, min_x, min_y, min_z, max_x, max_y, max_z):
        self._min_x = min_x
        self._min_y = min_y
        self._min_z = min_z
        self._max_x = max_x
        self._max_y = max_y
        self._max_z = max_z
        
      def __str__(self):
        return "\t( %f %f %f ) ( %f %f %f )\n" % \
          (self._min_x, self._min_y, self._min_z, self._max_x, self._max_y, self._max_z)

        
    def __init__(self):
      self._bounds = [] # bounding boxes for each frame

    def __str__(self):
      return "bounds {\n%s}\n\n" % \
        ("".join(str(element) for element in self._bounds))

    def Bound(self, min_x, min_y, min_z, max_x, max_y, max_z):
      created_bound = self._Bound(min_x, min_y, min_z, max_x, max_y, max_z)
      self._bounds.append(created_bound)
      return created_bound

      
  class BaseFrame(object):
    class _BasePosition(object):
      # ( pos.x pos.y pos.z ) ( orient.x orient.y orient.z )
      def __init__(self, pos_x, pos_y, pos_z, ori_x, ori_y, ori_z):
        self._pos_x = pos_x
        self._pos_y = pos_y
        self._pos_z = pos_z
        self._ori_x = ori_x
        self._ori_y = ori_y
        self._ori_z = ori_z

      def __str__(self):
        return "\t( %f %f %f ) ( %f %f %f )\n" % \
          (self._pos_x, self._pos_y, self._pos_z, self._ori_x, self._ori_y, self._ori_z)
        
    def __init__(self):
      self._basepositions = [] # position and orientation of bones
      
    def __str__(self):
      return "baseframe {\n%s}\n\n" % \
        ("".join([str(element) for element in self._basepositions]))

    def __len__(self):
      return len(self._basepositions)

    def BasePosition(self, pos_x, pos_y, pos_z, ori_x, ori_y, ori_z):
      created_baseposition = self._BasePosition(pos_x, pos_y, pos_z, ori_x, ori_y, ori_z)
      self._basepositions.append(created_baseposition)
      return created_baseposition
      
  class _Frame(object):
    class _FramePosition(object):
      # <float> <float> <float> <float> <float> <float> 
      def __init__(self, pos_x, pos_y, pos_z, ori_x, ori_y, ori_z):
        self._pos_x = pos_x
        self._pos_y = pos_y
        self._pos_z = pos_z
        self._ori_x = ori_x
        self._ori_y = ori_y
        self._ori_z = ori_z

      def __str__(self):
        return "\t%f %f %f %f %f %f\n" % \
          (self._pos_x, self._pos_y, self._pos_z, self._ori_x, self._ori_y, self._ori_z)
        
    def __init__(self, frameindex):
      self._frameindex = frameindex
      self._framepositions = [] # bone positions for frame

    def __str__(self):
      return "frame %i {\n%s}\n\n" % \
        (self._frameindex, "".join( [ str(element) for element in self._framepositions] ))

    def FramePosition(self, pos_x, pos_y, pos_z, ori_x, ori_y, ori_z):
      created_frameposition = self._FramePosition(pos_x, pos_y, pos_z, ori_x, ori_y, ori_z)
      self._framepositions.append(created_frameposition)
      return created_frameposition


  def __init__(self, commandline, framerate):
    super().__init__(commandline)
    self._framerate = framerate # frame rate
    self.Hierarchy = self.Hierarchy()
    self.Bounds = self.Bounds()
    self.BaseFrame = self.BaseFrame()
    self._frames = [] # list of frames

  def __str__(self):
    return "MD5Version %i\ncommandline \"%s\"\n\nnumFrames %i\nnumJoints %i\nframeRate %i\nnumAnimatedComponents %i\n\n%s%s%s%s" % \
      (self._version, self._commandline, len(self._frames), len(self.Hierarchy), self._framerate, len(self.BaseFrame), \
       str(self.Hierarchy), \
       str(self.Bounds), \
       str(self.BaseFrame), \
       "".join( [ str(element) for element in self._frames ] ))

  def Frame(self):
    created_frame = self._Frame(len(self._frames))
    self._frames.append(created_frame)
    return created_frame

# unit test for MD5MeshFormat
class MD5MeshFormatTest(object):
  def __init__(self):
    a = MD5MeshFormat('commandline from inline code')
    a.Joints.Joint('name', -1, -0.01, -0.01, -0.01, -0.01, -0.01, -0.01)
    new_mesh = a.Mesh("shader")
    new_vert = new_mesh.Vert(1, 2, 3, 4, 5)
    new_tri = new_mesh.Tri(0, 1, 2, 3)
    new_weight = new_mesh.Weight(1, 2, 3, 4, 5, 6)
    print(a)

# unit test for MD5AnimFormat
class MD5AnimFormatTest(object):
  def __init__(self):
    b = MD5AnimFormat('commandline from inline code', 24)
    b.Hierarchy.Joint('Legs', -1, 63, 0)
    b.Bounds.Bound(1 ,2 ,3 ,4, 5 ,6)
    b.BaseFrame.BasePosition(7, 8, 9, 1, 2, 3)
    new_frame = b.Frame()
    new_frame.FramePosition(7, 6, 5, 4, 3, 2)
    print(b)
  
################################################################################

class Component(object):
  #shader material
  class Material(object):
    name = ""		#string
    def __init__(self, textureFileName):
      self.name = textureFileName

    def to_md5mesh(self):
      return self.name;

  #the 'Model' class, contains all submeshes
  class Mesh(object):
    name = "" 		#string
    submeshes = []	#array of SubMesh
    next_submesh_id = 0	#int

    def __init__(self, name):
      self.name      = name
      self.submeshes = []

      self.next_submesh_id = 0


    def to_md5mesh(self):
      meshnumber=0
      buf = ""
      for submesh in self.submeshes:
        buf=buf + "mesh {\n"
  #      buf=buf + "mesh {\n\t// meshes: " + submesh.name + "\n"  # used for Sauerbraten -mikshaw
        meshnumber += 1
        buf=buf + submesh.to_md5mesh()
        buf=buf + "}\n\n"

      return buf


  #submeshes reference a parent mesh
  class SubMesh(object):
    def __init__(self, mesh, material):
      self.material   = material
      self.vertices   = []
      self.faces      = []
      self.nb_lodsteps = 0
      self.springs    = []
      self.weights    = []

      self.next_vertex_id = 0
      self.next_weight_id = 0

      self.mesh = mesh
      self.name = mesh.name
      self.id = mesh.next_submesh_id
      mesh.next_submesh_id += 1
      mesh.submeshes.append(self)

    def bindtomesh (self, mesh):
      # HACK: this is needed for md5 output, for the time being...
      # appending this submesh to the specified mesh, disconnecting it from the original one
      self.mesh.submeshes.remove(self)
      self.mesh = mesh
      self.id = mesh.next_submesh_id
      mesh.next_submesh_id += 1
      mesh.submeshes.append(self)

    def generateweights(self):
      self.weights = []
      self.next_weight_id = 0
      for vert in self.vertices:
        vert.generateweights()

    def reportdoublefaces(self):
      for face in self.faces:
        for face2 in self.faces:
          if not face == face2:
            if (not face.vertex1==face2.vertex1) and (not face.vertex1==face2.vertex2) and (not face.vertex1==face2.vertex3):
              return
            if (not face.vertex2==face2.vertex1) and (not face.vertex2==face2.vertex2) and (not face.vertex2==face2.vertex3):
              return
            if (not face.vertex3==face2.vertex1) and (not face.vertex3==face2.vertex2) and (not face.vertex3==face2.vertex3):
              return
            Typewriter.warn('Found doubleface: %s %s' % (face, face2))

    def to_md5mesh(self):
      self.generateweights()

      self.reportdoublefaces()

      buf="\tshader \"%s\"\n\n" % (self.material.to_md5mesh())
      if len(self.weights) == 0:
        buf=buf + "\tnumverts 0\n"
        buf=buf + "\n\tnumtris 0\n"
        buf=buf + "\n\tnumweights 0\n"
        return buf

      # output vertices
      buf=buf + "\tnumverts %i\n" % (len(self.vertices))
      vnumber=0
      for vert in self.vertices:
        buf=buf + "\tvert %i %s\n" % (vnumber, vert.to_md5mesh())
        vnumber += 1

      # output faces
      buf=buf + "\n\tnumtris %i\n" % (len(self.faces))
      facenumber=0
      for face in self.faces:
        buf=buf + "\ttri %i %s\n" % (facenumber, face.to_md5mesh())
        facenumber += 1

      # output weights
      buf=buf + "\n\tnumweights %i\n" % (len(self.weights))
      weightnumber=0
      for weight in self.weights:
        buf=buf + "\tweight %i %s\n" % (weightnumber, weight.to_md5mesh())
        weightnumber += 1

      return buf

  #vertex class contains and outputs 'verts' but also generates 'weights' data
  class Vertex(object):
    def __init__(self, submesh, loc, normal):
      self.loc    = loc
      self.normal = normal
      self.collapse_to         = None
      self.face_collapse_count = 0
      self.maps       = []
      self.influences = []
      self.weights = []
      self.weight = None
      self.firstweightindx = 0
      self.cloned_from = None
      self.clones      = []

      self.submesh = submesh
      self.id = submesh.next_vertex_id
      submesh.next_vertex_id += 1
      submesh.vertices.append(self)

    def generateweights(self):
      self.firstweightindx = self.submesh.next_weight_id
      for influence in self.influences:
        weightindx = self.submesh.next_weight_id
        self.submesh.next_weight_id += 1
        newweight = Component.Weight(influence.bone, influence.weight, self, weightindx, self.loc[0], self.loc[1], self.loc[2])
        self.submesh.weights.append(newweight)
        self.weights.append(newweight)

    def to_md5mesh(self):
      if self.maps:
        buf = self.maps[0].to_md5mesh()
      else:
        buf = "( %f %f )" % (self.loc[0], self.loc[1])
      buf = buf + " %i %i" % (self.firstweightindx, len(self.influences))
      return buf    

  #texture coordinate map 
  class Map(object):
    def __init__(self, u, v):
      self.u = u
      self.v = v


    def to_md5mesh(self):
      buf = "( %f %f )" % (self.u, self.v)
      return buf

  #NOTE: uses global 'scale' to scale the size of model verticies
  #generated and stored in Vertex class
  class Weight(object):
    def __init__(self, bone, weight, vertex, weightindx, x, y, z):
      self.bone = bone
      self.weight = weight
      self.vertex = vertex
      self.indx = weightindx
      invbonematrix = self.bone.matrix.transposed().inverted()
      self.x, self.y, self.z = mathutils.Vector((x, y, z))*invbonematrix

    def to_md5mesh(self):
      buf = "%i %f ( %f %f %f )" % (self.bone.id, self.weight, self.x*scale, self.y*scale, self.z*scale)
      return buf

  #used by SubMesh class
  class Influence(object):
    def __init__(self, bone, weight):
      self.bone   = bone
      self.weight = weight

  #outputs the 'tris' data
  class Face(object):
    def __init__(self, submesh, vertex1, vertex2, vertex3):
      self.vertex1 = vertex1
      self.vertex2 = vertex2
      self.vertex3 = vertex3

      self.can_collapse = 0

      self.submesh = submesh
      submesh.faces.append(self)


    def to_md5mesh(self):
      buf = "%i %i %i" % (self.vertex1.id, self.vertex3.id, self.vertex2.id)
      return buf

  #holds bone skeleton data and outputs header above the Mesh class
  class Skeleton(object):
    def __init__(self, MD5Version = 10, commandline = "OpenTechEngine MD5 format - https://github.com/OpenTechEngine/ModelingTools"):
      self.bones = []
      self.MD5Version = MD5Version
      self.commandline = commandline
      self.next_bone_id = 0


    def to_md5mesh(self, numsubmeshes):
      buf = "MD5Version %i\n" % (self.MD5Version)
      buf = buf + "commandline \"%s\"\n\n" % (self.commandline)
      buf = buf + "numJoints %i\n" % (self.next_bone_id)
      buf = buf + "numMeshes %i\n\n" % (numsubmeshes)
      buf = buf + "joints {\n"
      for bone in self.bones:
        buf = buf + bone.to_md5mesh()
      buf = buf + "}\n\n"
      return buf

  #held by Skeleton, generates individual 'joint' data
  class Bone(object):
    def __init__(self, skeleton, parent, name, mat, theboneobj):
      self.parent = parent #Bone
      self.name   = name   #string
      self.children = []   #list of Bone objects
      self.theboneobj = theboneobj #Blender.Armature.Bone
      self.is_animated = 0  # is there an ipo that animates this bone

      self.matrix = mat
      if parent:
        parent.children.append(self)

      self.skeleton = skeleton
      self.id = skeleton.next_bone_id
      skeleton.next_bone_id += 1
      skeleton.bones.append(self)

    def to_md5mesh(self):
      global scale
      buf= "\t\"%s\"\t" % (self.name)
      parentindex = -1
      if self.parent:
          parentindex=self.parent.id
      buf=buf+"%i " % (parentindex)

      pos1, pos2, pos3= self.matrix.col[3][0], self.matrix.col[3][1], self.matrix.col[3][2]
      buf=buf+"( %f %f %f ) " % (pos1*scale, pos2*scale, pos3*scale)
      #qx, qy, qz, qw = matrix2quaternion(self.matrix)
      #if qw<0:
      #    qx = -qx
      #    qy = -qy
      #    qz = -qz
      m = self.matrix
  #    bquat = self.matrix.to_quat()  #changed from matrix.toQuat() in blender 2.4x script
      bquat = self.matrix.to_quaternion()  #changed from to_quat in 2.57 -mikshaw
      bquat.normalize()
      qx = bquat.x
      qy = bquat.y
      qz = bquat.z
      if bquat.w > 0:
          qx = -qx
          qy = -qy
          qz = -qz
      buf=buf+"( %f %f %f )\t\t// " % (qx, qy, qz)
      if self.parent:
          buf=buf+"%s" % (self.parent.name)    

      buf=buf+"\n"
      return buf


  class Animation(object):
    def __init__(self, md5skel, MD5Version = 10, commandline = "OpenTechEngine MD5 format - https://github.com/OpenTechEngine/ModelingTools"):
      self.framedata    = [] # framedata[boneid] holds the data for each frame
      self.bounds       = []
      self.baseframe    = []
      self.skeleton     = md5skel
      self.boneflags    = []  # stores the md5 flags for each bone in the skeleton
      self.boneframedataindex = [] # stores the md5 framedataindex for each bone in the skeleton
      self.MD5Version   = MD5Version
      self.commandline  = commandline
      self.numanimatedcomponents = 0
      self.framerate    = 24
      self.numframes    = 0
      for b in self.skeleton.bones:
        self.framedata.append([])
        self.baseframe.append([])
        self.boneflags.append(0)
        self.boneframedataindex.append(0)

    def to_md5anim(self):
      currentframedataindex = 0
      for bone in self.skeleton.bones:
        if (len(self.framedata[bone.id])>0):
          if (len(self.framedata[bone.id])>self.numframes):
            self.numframes=len(self.framedata[bone.id])
          (x,y,z),(qw,qx,qy,qz) = self.framedata[bone.id][0]
          self.baseframe[bone.id]= (x*scale,y*scale,z*scale,qx,qy,qz)
          self.boneframedataindex[bone.id]=currentframedataindex
          self.boneflags[bone.id] = 63
          currentframedataindex += 6
          self.numanimatedcomponents = currentframedataindex
        else:
          rot=bone.matrix.to_quaternion()
          rot.normalize()
          qx=rot.x
          qy=rot.y
          qz=rot.z
          if rot.w > 0:
              qx = -qx
              qy = -qy
              qz = -qz            
          self.baseframe.col[bone.id]= (bone.matrix.col[3][0]*scale, bone.matrix.col[3][1]*scale, bone.matrix.col[3][2]*scale, qx, qy, qz)

      buf = "MD5Version %i\n" % (self.MD5Version)
      buf = buf + "commandline \"%s\"\n\n" % (self.commandline)
      buf = buf + "numFrames %i\n" % (self.numframes)
      buf = buf + "numJoints %i\n" % (len(self.skeleton.bones))
      buf = buf + "frameRate %i\n" % (self.framerate)
      buf = buf + "numAnimatedComponents %i\n\n" % (self.numanimatedcomponents)
      buf = buf + "hierarchy {\n"

      for bone in self.skeleton.bones:
        parentindex = -1
        flags = self.boneflags[bone.id]
        framedataindex = self.boneframedataindex[bone.id]
        if bone.parent:
          parentindex=bone.parent.id
        buf = buf + "\t\"%s\"\t%i %i %i\t//" % (bone.name, parentindex, flags, framedataindex)
        if bone.parent:
          buf = buf + " " + bone.parent.name
        buf = buf + "\n"
      buf = buf + "}\n\n"

      buf = buf + "bounds {\n"
      for b in self.bounds:
        buf = buf + "\t( %f %f %f ) ( %f %f %f )\n" % (b)
      buf = buf + "}\n\n"

      buf = buf + "baseframe {\n"
      for b in self.baseframe:
        buf = buf + "\t( %f %f %f ) ( %f %f %f )\n" % (b)
      buf = buf + "}\n\n"

      for f in range(0, self.numframes):
        buf = buf + "frame %i {\n" % (f)
        for b in self.skeleton.bones:
          if (len(self.framedata[b.id])>0):
            (x,y,z),(qw,qx,qy,qz) = self.framedata[b.id][f]
            if qw>0:
              qx,qy,qz = -qx,-qy,-qz
            buf = buf + "\t%f %f %f %f %f %f\n" % (x*scale, y*scale, z*scale, qx,qy,qz)
        buf = buf + "}\n\n"

      return buf

    def addkeyforbone(self, boneid, time, loc, rot):
      # time is ignored. the keys are expected to come in sequentially
      # it might be useful for future changes or modifications for other export formats
      self.framedata[boneid].append((loc, rot))
      return



    def generateboundingbox(objects, md5animation, framerange):
      scene = bpy.context.scene #Blender.Scene.getCurrent()
      context = scene.render #scene.getRenderingContext()
      for i in range(framerange[0], framerange[1]+1):
        corners = []
        #context.currentFrame(i)
        #scene.makeCurrent()
        scene.frame_set( i ) 

        for obj in objects:
          data = obj.data #obj.getData()
          #if (type(data) is Blender.Types.NMeshType) and data.faces:
          if obj.type == 'MESH' and data.polygons:
            #obj.makeDisplayList()
            #(lx, ly, lz) = obj.getLocation()
            (lx, ly, lz ) = obj.location
            #bbox = obj.getBoundBox()
            bbox = obj.bound_box
            matrix = mathutils.Matrix([[1.0,  0.0, 0.0, 0.0],
              [0.0,  1.0, 0.0, 0.0],
              [0.0,  1.0, 1.0, 0.0],
              [0.0,  0.0, 0.0, 1.0],
              ])
            # original matrix from the 2.61 compatible script
            # matrix.transpose()
            for v in bbox:
              vecp = mathutils.Vector((v[0], v[1], v[2]))
              corners.append(vecp*matrix)
              #corners.append(MD5Math.point_by_matrix (v, matrix))

        (min, max) = MD5Math.getminmax(corners)
        md5animation.bounds.append((min[0]*scale, min[1]*scale, min[2]*scale, max[0]*scale, max[1]*scale, max[2]*scale))
  
    
#exporter settings
class MD5Settings(object):
  def __init__(self, savepath, exportMode, scale=1.0):
    self.savepath = savepath
    self.exportMode = exportMode
    self.scale = scale

class MD5Save(object):
  def __init__(self, settings):
    self.settings = settings
    self.thearmature = None  #null to start, will assign in next section || TODO check if limiting for multiple meshes
    self.skeleton = 0
    self.meshes = []
    self.ANIMATIONS = 0
    self.rangestart = 0
    self.rangeend = 0
    self.BONES = {}

    
  def armature(self):

    #first pass on selected data, pull one skeleton
    self.skeleton = Component.Skeleton()
    bpy.context.scene.frame_set(bpy.context.scene.frame_start)
    for obj in bpy.context.selected_objects:
      if obj.type == 'ARMATURE':
        #skeleton.name = obj.name
        self.thearmature = obj
        w_matrix = obj.matrix_world

        #define recursive bone parsing function
        def treat_bone(b, parent = None):
          if (parent and not b.parent.name==parent.name):
            return #only catch direct children

          mat =  mathutils.Matrix(w_matrix) * mathutils.Matrix(b.matrix_local)  #reversed order of multiplication from 2.4 to 2.5

          bone = Component.Bone(self.skeleton, parent, b.name, mat, b)
          # insert into class bone list
          self.BONES[bone.name] = bone

          if( b.children ):
            for child in b.children: treat_bone(child, bone)

        for b in self.thearmature.data.bones:
          if( not b.parent ): #only treat root bones'
            Typewriter.info( "Root bone: " + b.name )
            treat_bone(b)

        break #only pull one skeleton out
      
  def mesh(self):
    #second pass on selected data, pull meshes
    
    for obj in bpy.context.selected_objects:
      if ((obj.type == 'MESH') and ( len(obj.data.vertices.values()) > 0 )):
        #for each non-empty mesh
        mesh = Component.Mesh(obj.name)
        obj.data.update(calc_tessface=True)
        Typewriter.info( "Processing mesh: "+ obj.name )
        self.meshes.append(mesh)

        numTris = 0
        numWeights = 0
        for f in obj.data.polygons:
          numTris += len(f.vertices) - 2
        for v in obj.data.vertices:
          numWeights += len( v.groups )

        w_matrix = obj.matrix_world
        verts = obj.data.vertices

        uv_textures = obj.data.tessface_uv_textures
        faces = []
        for f in obj.data.polygons:
          faces.append( f )

        createVertexA = 0
        createVertexB = 0
        createVertexC = 0

        while faces:
          material_index = faces[0].material_index
          material = Component.Material(obj.data.materials[0].name ) #call the shader name by the material's name

          submesh = Component.SubMesh(mesh, material)
          vertices = {}
          for face in faces[:]:
            # der_ton: i added this check to make sure a face has at least 3 vertices.
            # (pdz) also checks for and removes duplicate verts
            if len(face.vertices) < 3: # throw away faces that have less than 3 vertices
              faces.remove(face)
            elif face.vertices[0] == face.vertices[1]:  #throw away degenerate triangles
              faces.remove(face)
            elif face.vertices[0] == face.vertices[2]:
              faces.remove(face)
            elif face.vertices[1] == face.vertices[2]:
              faces.remove(face)
            elif face.material_index == material_index:
              #all faces in each sub-mesh must have the same material applied
              faces.remove(face)

              if not face.use_smooth :
                p1 = verts[ face.vertices[0] ].co
                p2 = verts[ face.vertices[1] ].co
                p3 = verts[ face.vertices[2] ].co

                vector1 = mathutils.Vector((p3[0] - p2[0], p3[1] - p2[1], p3[2] - p2[2]))
                vector2 = mathutils.Vector((p1[0] - p2[0], p1[1] - p2[1], p1[2] - p2[2]))
                vectorcp = mathutils.Vector.cross(vector1, vector2)

                normal = mathutils.Vector.normalize(vectorcp*w_matrix)

              #for each vertex in this face, add unique to vertices dictionary
              face_vertices = []
              for i in range(len(face.vertices)):
                vertex = False
                if face.vertices[i] in vertices: 
                  vertex = vertices[  face.vertices[i] ] #type of Vertex
                  
                if not vertex: #found unique vertex, add to list
                  coord = (verts[face.vertices[i]].co)*w_matrix #TODO: fix possible bug here ?

                  if face.use_smooth:
                    normal = mathutils.Vector.normalize((verts[face.vertices[i]].normal)*w_matrix)
                    
                  vertex  = vertices[face.vertices[i]] = Component.Vertex(submesh, coord, normal) 
                  createVertexA += 1

                  influences = []
                  for j in range(len( obj.data.vertices[ face.vertices[i] ].groups )):
                    inf = [obj.vertex_groups[ obj.data.vertices[ face.vertices[i] ].groups[j].group ].name, obj.data.vertices[ face.vertices[i] ].groups[j].weight]
                    influences.append( inf )

                  if not influences:
                    Typewriter.warn( "There is a vertex without attachment to a bone in mesh: " + mesh.name )
                  sum = 0.0
                  for bone_name, weight in influences: sum += weight

                  for bone_name, weight in influences:
                    if sum != 0:
                      try:
                          vertex.influences.append(Component.Influence(self.BONES[bone_name], weight / sum))
                      except:
                          continue
                    else: # we have a vertex that is probably not skinned. export anyway
                      try:
                        vertex.influences.append(Component.Influence(self.BONES[bone_name], weight)) # TODO warn?
                      except:
                        Typewriter.warn("Vertex without UV : "+str(self.BONES[bone_name])+" weight "+str(weight))
                        continue

                  #print( "vert " + str( face.vertices[i] ) + " has " + str(len( vertex.influences ) ) + " influences ")

                elif not face.use_smooth:
                  # We cannot share vertex for non-smooth faces, since Cal3D does not
                  # support vertex sharing for 2 vertices with different normals.
                  # => we must clone the vertex.

                  old_vertex = vertex
                  vertex = Component.Vertex(submesh, vertex.loc, normal)
                  createVertexB += 1
                  vertex.cloned_from = old_vertex
                  vertex.influences = old_vertex.influences
                  old_vertex.clones.append(vertex)

                hasFaceUV = len(uv_textures) > 0 #borrowed from export_obj.py

                if hasFaceUV: 
                  uv = [uv_textures.active.data[face.index].uv[i][0], uv_textures.active.data[face.index].uv[i][1]]
                  uv[1] = 1.0 - uv[1]  # should we flip Y? yes, new in Blender 2.5x
                  if not vertex.maps: vertex.maps.append(Component.Map(*uv))
                  elif (vertex.maps[0].u != uv[0]) or (vertex.maps[0].v != uv[1]):
                    # This vertex can be shared for Blender, but not for MD5
                    # MD5 does not support vertex sharing for 2 vertices with
                    # different UV texture coodinates.
                    # => we must clone the vertex.

                    for clone in vertex.clones:
                      if (clone.maps[0].u == uv[0]) and (clone.maps[0].v == uv[1]):
                        vertex = clone
                        break
                    else: # Not yet cloned...  (PDZ) note: this ELSE belongs attached to the FOR loop.. python can do that apparently
                      old_vertex = vertex
                      vertex = Component.Vertex(submesh, vertex.loc, vertex.normal)
                      createVertexC += 1
                      vertex.cloned_from = old_vertex
                      vertex.influences = old_vertex.influences
                      vertex.maps.append(Component.Map(*uv))
                      old_vertex.clones.append(vertex)

                face_vertices.append(vertex)

              # Split faces with more than 3 vertices
              for i in range(1, len(face.vertices) - 1):
                Component.Face(submesh, face_vertices[0], face_vertices[i], face_vertices[i + 1])
            else:
              Typewriter.warn( "Face with invalid material: "+str(face))
        Typewriter.info( "Created verts at A " + str(createVertexA) + ", B " + str( createVertexB ) + ", C " + str( createVertexC ) )


  def anim(self):

    # Export animations

    # perhaps get proper actions via bpy.data.actions?
    # .selected_objects[0].animation_data.action.fcurves[__iter__].sampled_points.data.is_valid
    
    self.ANIMATIONS = {}

    arm_action = self.thearmature.animation_data.action
    if arm_action:
      animation = self.ANIMATIONS[arm_action.name] = Component.Animation(self.skeleton)
  #    armature.animation_data.action = action
      bpy.context.scene.update()
      armature = bpy.context.active_object
      action = armature.animation_data.action
  #    framemin, framemax	= bpy.context.active_object.animation_data.Action(fcurves.frame_range)
      framemin, framemax  = action.frame_range
      self.rangestart = int(framemin)
      self.rangeend = int(framemax)
  #    rangestart = int( bpy.context.scene.frame_start ) # int( arm_action.frame_range[0] )
  #    rangeend = int( bpy.context.scene.frame_end ) #int( arm_action.frame_range[1] )
      currenttime = self.rangestart
      while currenttime <= self.rangeend: 
        bpy.context.scene.frame_set(currenttime)
        time = (currenttime - 1.0) / 24.0 #(assuming default 24fps for md5 anim)
        pose = self.thearmature.pose

        for bonename in self.thearmature.data.bones.keys():
          posebonemat = mathutils.Matrix(pose.bones[bonename].matrix ) # @ivar poseMatrix: The total transformation of this PoseBone including constraints. -- different from localMatrix

          try:
            bone  = self.BONES[bonename] #look up md5bone
          except:
            Typewriter.warn( "Found a PoseBone animating a bone that is not part of the exported armature: " + bonename )
            continue
          if bone.parent: # need parentspace-matrix
            parentposemat = mathutils.Matrix(pose.bones[bone.parent.name].matrix ) # @ivar poseMatrix: The total transformation of this PoseBone including constraints. -- different from localMatrix
  #          posebonemat = parentposemat.invert() * posebonemat #reverse order of multiplication!!!
            parentposemat.invert() # mikshaw
            posebonemat = parentposemat * posebonemat # mikshaw
          else:
            posebonemat = self.thearmature.matrix_world * posebonemat  #reverse order of multiplication!!!
          loc = [posebonemat.col[3][0],
              posebonemat.col[3][1],
              posebonemat.col[3][2],
              ]
  #        rot = posebonemat.to_quat().normalize()
          rot = posebonemat.to_quaternion() # changed from to_quat in 2.57 -mikshaw
          rot.normalize() # mikshaw
          rot = [rot.w,rot.x,rot.y,rot.z]

          animation.addkeyforbone(bone.id, time, loc, rot)
        currenttime += 1

  def export_mesh(self):
    md5mesh_filename = self.settings.savepath + ".md5mesh"

    #save all submeshes in the first mesh
    if len(self.meshes)>1:
      for mesh in range (1, len(self.meshes)):
        for submesh in self.meshes[mesh].submeshes:
          submesh.bindtomesh(self.meshes[0])
    if (md5mesh_filename != ""):
      file = open(md5mesh_filename, 'w')
      buffer = self.skeleton.to_md5mesh(len(self.meshes[0].submeshes))
      #for mesh in meshes:
      buffer = buffer + self.meshes[0].to_md5mesh()
      file.write(buffer)
      file.close()
      Typewriter.info( "Saved mesh to " + md5mesh_filename )
    else:
      Typewriter.error( "No md5mesh file was generated." )

  def export_anim(self):
    md5anim_filename = self.settings.savepath + ".md5anim"

    #save animation file
    if len(self.ANIMATIONS)>0:
      anim = self.ANIMATIONS.popitem()[1] #ANIMATIONS.values()[0]
      Typewriter.info("Animation "+ str( anim ) )
      file = open(md5anim_filename, 'w')
      objects = []
      for submesh in self.meshes[0].submeshes:
        if len(submesh.weights) > 0:
          obj = None
          for sob in bpy.context.selected_objects:
              if sob and sob.type == 'MESH' and sob.name == submesh.name:
                obj = sob
          objects.append (obj)
      Component.Animation.generateboundingbox(objects, anim, [self.rangestart, self.rangeend])
      buffer = anim.to_md5anim()
      file.write(buffer)
      file.close()
      Typewriter.info( "Saved anim to " + md5anim_filename )
    else:
      Typewriter.error( "No md5anim file was generated." )

  # serializer function
  def save_md5(self):
    Typewriter.info("Exporting selected objects...")
    bpy.ops.object.mode_set(mode='OBJECT')

    scale = self.settings.scale

    # construct armature, mesh and anim to our Components
    self.armature()
    self.mesh()
    self.anim()

    # here begins md5mesh and anim output
    # first the skeleton is output, using the data that was collected by the above code in this export function
    # then the mesh data is output (into the same md5mesh file)

    if( self.settings.exportMode == "mesh & anim" or self.settings.exportMode == "mesh only" ):
      self.export_mesh()
    elif( self.settings.exportMode == "mesh & anim" or self.settings.exportMode == "anim only" ):
      self.export_anim()
    
              
  
##########
#export class registration and interface
class ExportMD5(bpy.types.Operator):
  '''Export to idTech 4 MD5 (.md5mesh .md5anim)'''
  bl_idname = "export.md5"
  bl_label = 'idTech 4 MD5'
  
  logenum = [("console","Console","log to console"),
             ("append","Append","append to log file"),
             ("overwrite","Overwrite","overwrite log file")]
             
  #search for list of actions to export as .md5anims
  #md5animtargets = []
  #for anim in bpy.data.actions:
  #	md5animtargets.append( (anim.name, anim.name, anim.name) )
  	
  #md5animtarget = None
  #if( len( md5animtargets ) > 0 ):
  #	md5animtarget = EnumProperty( name="Anim", items = md5animtargets, description = "choose animation to export", default = md5animtargets[0] )
  	
  exportModes = [("mesh & anim", "Mesh & Anim", "Export .md5mesh and .md5anim files."),
  		 ("anim only", "Anim only.", "Export .md5anim only."),
  		 ("mesh only", "Mesh only.", "Export .md5mesh only.")]

  filepath = StringProperty(subtype = 'FILE_PATH',name="File Path", description="Filepath for exporting", maxlen= 1024, default= "")
  md5name = StringProperty(name="MD5 Name", description="MD3 header name / skin path (64 bytes)",maxlen=64,default="")
  md5exportList = EnumProperty(name="Exports", items=exportModes, description="Choose export mode.", default='mesh & anim')
  #md5logtype = EnumProperty(name="Save log", items=logenum, description="File logging options",default = 'console')
  md5scale = FloatProperty(name="Scale", description="Scale all objects from world origin (0,0,0)", min=0.001, max=1000.0, default=1.0,precision=6)
  #md5offsetx = FloatProperty(name="Offset X", description="Transition scene along x axis",default=0.0,precision=5)
  #md5offsety = FloatProperty(name="Offset Y", description="Transition scene along y axis",default=0.0,precision=5)
  #md5offsetz = FloatProperty(name="Offset Z", description="Transition scene along z axis",default=0.0,precision=5)

  def setup_typewriter(self):
    def print_info(message):
      self.report({'INFO'}, message)

    def print_warn(message):
      self.report({'WARNING'}, message)

    def print_error(message):
      self.report({'ERROR'}, message)

    Typewriter.info = print_info
    Typewriter.warn = print_warn
    Typewriter.error = print_error

  def execute(self, context):
    # FIXME bug, exports only one, GUI enters only one filepath
    self.setup_typewriter()
    global scale
    scale = self.md5scale
    settings = MD5Settings(savepath = self.properties.filepath,
                           exportMode = self.properties.md5exportList
                           )
    serializer = MD5Save(settings)
    serializer.save_md5()

    return {'FINISHED'}

  def invoke(self, context, event):
        WindowManager = context.window_manager
        # fixed for 2.56? Katsbits.com (via Nic B)
        # original WindowManager.add_fileselect(self)
        WindowManager.fileselect_add(self)
        return {"RUNNING_MODAL"}  

class console(object):
  # blender uses it's own, can't override it so we set it only here
  def exception_handler(self, type, value, trace):
    Typewriter.error(''.join(traceback.format_tb(trace)))
    Typewriter.error(type.__name__+": "+str(value))
  
  def get_parameters(self):
    accepted_arguments = ["output-dir=", "scale=", "mesh=", "help"]

    def print_executed_string():
      Typewriter.info("Executed string: "+" ".join(sys.argv))

    def usage():
      Typewriter.info('Usage: blender file.blend --background --python io_export_md5.py -- --arg1 val1 --arg2 val2')
      Typewriter.info("Available arguments")
      for argument in accepted_arguments:
        Typewriter.info("\t--"+argument)

    # check if '--' entered, arguments after that are for us
    dashes_at = 0
    i = 0
    for arg in sys.argv:
      if arg == "--":
        dashes_at = i+1
      i = i+1
    if dashes_at == 0:
      usage()

    # if no valid arguments entered, print usage
    try:
      opts, args  = getopt.getopt(sys.argv[dashes_at:], "", accepted_arguments)
    except getopt.GetoptError as err:
      print_executed_string()
      Typewriter.error(str(err))
      usage()
      sys.exit(2)

    for opt, arg in opts:
      if opt == '--output-dir':
        self.output_dir = arg
        if os.access(self.output_dir, os.W_OK) == False:
          print_executed_string()
          Typewriter.error('Cannot write to folder: '+self.output_dir)
          sys.exit(2)
      if opt == '--scale':
        try:
          self.scale = float(arg)
        except ValueError:
          print_executed_string()
          Typewriter.error("--scale expected float, received: "+arg)
          sys.exit(2)
      if opt == '--mesh':
        self.mesh_name = arg

      if opt == '--help':
        usage()
        sys.exit(0)

  def export(self):
    objList = [object for object in bpy.context.scene.objects if object.type == 'MESH']
    export_count = 0
    for ob in objList:
      if ob.name == self.mesh_name or not self.mesh_name:
        Typewriter.info("Selected object: "+ob.name)
        ob.select = True
        if ob.type == "MESH":
          serializer = MD5Save(MD5Settings(savepath=self.output_dir+"/"+ob.name, exportMode="mesh & anim"))
          serializer.save_md5()
          ob.select = False
          export_count = export_count + 1
          Typewriter.info("Exported: "+ob.name+"\n")

    if self.mesh_name and export_count == 0:
      Typewriter.error("No such mesh: "+self.mesh_name)
      sys.exit(2)
    else:
      Typewriter.info("Exported "+str(export_count)+" mesh(es).")
      sys.exit(0)

  def __init__(self):
    self.output_dir = os.getcwd()
    self.scale = 1.00
    self.mesh_name = ''

    sys.excepthook = self.exception_handler
    self.get_parameters()

    # global scale parameter
    global scale
    scale = self.scale
    
    self.export()


# blender gui module function
def menu_func(self, context):
  default_path = os.path.splitext(bpy.data.filepath)[0]
  self.layout.operator(ExportMD5.bl_idname, text="idTech 4 MD5 (.md5mesh .md5anim)", icon='BLENDER').filepath = default_path

# blender gui module register  
def register():
  bpy.utils.register_module(__name__)
  bpy.types.INFO_MT_file_export.append(menu_func)

# blender gui module unregister  
def unregister():
  bpy.utils.unregister_module(__name__)
  bpy.types.INFO_MT_file_export.remove(menu_func)

# running as external script
if __name__ == "__main__":
  MD5MeshFormatTest()
  MD5AnimFormatTest()
  console()
