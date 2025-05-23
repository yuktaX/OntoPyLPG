from owlready2 import *
from py2neo import Graph, Node, Relationship
from .OWLHelper import OWLHelper
# from Connector import Connector

class Mapper:
   
   def __init__(self, neo4j_graph, filename, format):

      self.neo4j_graph = neo4j_graph
      self.owl_helper = OWLHelper(filename, format)
      self.onto = self.owl_helper.load_owl_ontology()
      self.nodes = {}

   def process_classes(self):
      
      for cls in self.onto.classes():
         class_name = self.owl_helper.extract_local_name(cls.iri)
         
         # Create a Neo4j node for this class and add it to graph it if it doesn't exist
         class_node = Node("Class", name=class_name)
         self.neo4j_graph.create(class_node)
         self.nodes[cls.iri] = class_node
          
   def process_subclass_relationships(self):
      
      for subclass in self.onto.classes():
         for superclass in subclass.is_a:    # Iterate over all superclasses (is_a relationships)
            if superclass in self.onto.classes():  # Ensure the superclass is a valid class
               
               # Extract the local names of the subclass and superclass
               subclass_name = self.owl_helper.extract_local_name(subclass.iri)
               superclass_name = self.owl_helper.extract_local_name(superclass.iri)
               
               # Fetch or create the self.nodes for subclass and superclass
               subclass_node = self.nodes.get(subclass.iri)  # Using the existing node for the subclass
               superclass_node = self.nodes.get(superclass.iri)  # Using the existing node for the superclass
               
               if not subclass_node:
                     subclass_node = Node("Class", name=subclass_name)
                     self.neo4j_graph.create(subclass_node)
                     self.nodes[subclass.iri] = subclass_node
               
               if not superclass_node:
                     superclass_node = Node("Class", name=superclass_name)
                     self.neo4j_graph.create(superclass_node)
                     self.nodes[superclass.iri] = superclass_node  
                     
               # Create a relationship between subclass and superclass (if not already created)
               rel = Relationship(subclass_node, "SUBCLASS_OF", superclass_node)
               self.neo4j_graph.merge(rel)
               print(f"Creating SUBCLASS_OF: {subclass_name} --> {superclass_name}")

   def process_object_properties(self):
      
      for prop in self.onto.object_properties():
         
         all_props = [prop]
         all_props.extend(prop.is_a)
         
         for superprop in all_props:
            prop_name = superprop.name
            if prop_name not in ["ObjectProperty", "TransitiveProperty"]:
         
               # If prop doesnt have domain range use the child domain range
               domain = superprop.domain if superprop.domain else prop.domain
               range = superprop.range if superprop.range else prop.range
               
               for domain_class in domain:
                  for range_class in range:

                     d_cls, r_cls = domain_class, range_class
                     
                     if isinstance(d_cls,Restriction) or isinstance(r_cls,Restriction):    #remove the cls != domain_class if you want all sub classes to also be considered
                           continue
                     
                     d_cls_name = self.owl_helper.extract_local_name(d_cls.iri)
                     r_cls_name = self.owl_helper.extract_local_name(r_cls.iri)
                     
                     # Fetch or create the domain class node
                     d_cls_node = self.nodes.get(d_cls.iri)
                     if not d_cls_node:
                        d_cls_node = Node("Class", name=d_cls_name)
                        self.neo4j_graph.merge(d_cls_node)
                        self.nodes[d_cls.iri] = d_cls_node  

                     # Fetch or create the range class node
                     r_cls_node = self.nodes.get(r_cls.iri)
                     if not r_cls_node:
                        r_cls_node = Node("Class", name=r_cls_name)
                        self.neo4j_graph.create(r_cls_node)
                        self.nodes[r_cls.iri] = r_cls_node  
                        
                     # Create a relationship between the domain (or domain subclass) and range using the property name
                     print(f"Creating Relationship: {d_cls_name} --{prop_name.upper()}--> {r_cls_name}")
                     rel = Relationship(d_cls_node, prop_name.upper(), r_cls_node)
                     self.neo4j_graph.merge(rel)
               
           
   def process_individuals(self):
    for individual in self.onto.individuals():
      individual_name = self.owl_helper.extract_local_name(individual.iri)

      # Create a Neo4j node for this individual
      individual_node = self.nodes.get(individual.iri)
      if not individual_node:
            individual_node = Node("Individual", name=individual_name)
            self.neo4j_graph.create(individual_node)
            self.nodes[individual.iri] = individual_node 
      
      #Adding object property edges
      for prop in self.onto.object_properties():
        values = list(prop[individual])
        for v in values:
            print(f"Individual obj props  {prop.name} -> {[v.name]}")
            v_name = self.owl_helper.extract_local_name(v.iri)
            v_node = self.nodes.get(v.iri)
            if not v_node:
               v_node = Node("Class",name=v_name)
               self.neo4j_graph.create(v_node)
               self.nodes[v.iri] = v_node
            
            rel = Relationship(individual_node,prop.name.upper(),v_node)
            self.neo4j_graph.merge(rel)
            print(f"Created relationship with for {v_name} {individual_name}")

      # Process class/subclass relationships
      for cls in individual.is_a:
            if cls in self.onto.classes():
               class_name = self.owl_helper.extract_local_name(cls.iri)

               # Use or create class node
               class_node = self.nodes.get(cls.iri)
               if not class_node:
                  class_node = Node("Class", name=class_name)
                  self.neo4j_graph.merge(class_node, "Class", "name")
                  self.nodes[cls.iri] = class_node

               # Create INSTANCE_OF relationship
               rel = Relationship(individual_node, "INSTANCE_OF", class_node)
               self.neo4j_graph.merge(rel)
               print(f"Creating INSTANCE_OF: {individual_name} --> {class_name}")

      # Process data properties 
      for prop in individual.get_properties():
            for value in prop[individual]:

                  # If Data property, set it on node
                  if isinstance(value, (str, int, float, bool)):  
                     individual_node[prop.name] = value
                     self.neo4j_graph.push(individual_node)

   def process_subclass_restrictions(self):
        
        for cls in self.onto.classes():
            cls_name = self.owl_helper.extract_local_name(cls.iri)

            # Fetch or create the domain class node
            cls_node = self.nodes.get(cls.iri)
            if not cls_node:
                cls_node = Node("Class", name=cls_name)
                self.neo4j_graph.merge(cls_node, "Class", "name")
                self.nodes[cls.iri] = cls_node

            for superclass in cls.is_a:
                # Check if it is a "some" restriction (ObjectSomeValuesFrom)
                if isinstance(superclass, owlready2.Restriction) and superclass.type == SOME:
                    prop = superclass.property  # Object Property
                    target_cls = superclass.value     # Range Class

                    if isinstance(target_cls, ThingClass):  # Ensure target_cls is a class, not an instance
                        target_cls_name = self.owl_helper.extract_local_name(target_cls.iri)

                        # Fetch or create the range class node
                        target_cls_node = self.nodes.get(target_cls.iri)
                        if not target_cls_node:
                            target_cls_node = Node("Class", name=target_cls_name)
                            self.neo4j_graph.merge(target_cls_node, "Class", "name")
                            self.nodes[target_cls.iri] = target_cls_node

                        # Create relationship
                        prop_name = self.owl_helper.extract_local_name(prop.iri)
                        rel = Relationship(cls_node, prop_name.upper(), target_cls_node)
                        self.neo4j_graph.create(rel)

                        print(f"Created relationship: {cls_name} -[:{prop_name.upper()}]-> {target_cls_name}")

   def process_cardinality_data(self):
    for d_cls in self.onto.classes():
        d_cls_name = self.owl_helper.extract_local_name(d_cls.iri)

        # Fetch or create domain class node
        d_cls_node = self.nodes.get(d_cls.iri)
        if not d_cls_node:
            d_cls_node = Node("Class", name=d_cls_name)
            self.neo4j_graph.merge(d_cls_node)
            self.nodes[d_cls.iri] = d_cls_node

        for superclass in d_cls.is_a:
            if isinstance(superclass, Restriction):
                prop = superclass.property
                prop_name = self.owl_helper.extract_local_name(prop.iri)

                if superclass.type in [MIN, MAX, EXACTLY]:
                    # Determine the type and value of restriction
                    restriction_type = {
                        MIN: "min",
                        MAX: "max",
                        EXACTLY: "exact"
                    }[superclass.type]

                    cardinality = int(superclass.cardinality)

                    # Create a new property on the class node to store the restriction
                    restriction_key = f"has_cardinality_{prop_name}"
                    restriction_value = f"{restriction_type}:{cardinality}"
                    d_cls_node[restriction_key] = restriction_value

                    # Push updated class node to Neo4j
                    self.neo4j_graph.push(d_cls_node)

                    print(f"Added cardinality info on {d_cls_name}: {restriction_key} = {restriction_value}")

   def map_all(self):
      
      # Step 1: Process OWL Classes and Create LPG Nodes
      self.process_classes()
      
      # Step 2: Process Subclass Relationships
      self.process_subclass_relationships()

      # Step 3: Process individuals
      self.process_individuals()

      # Step 4: Process Object Properties (Relationships)
      self.process_object_properties()

      # Step 5: Process subclass restrictions
      self.process_subclass_restrictions()

      # Step 7: Add cardinality restrictions
      self.process_cardinality_data()

      print("OWL to LPG Conversion Complete!")
      