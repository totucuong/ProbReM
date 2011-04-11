'''
INSTRUCTIONS to recreate/update/modify the artificial dataset:

    If you want to change the skeleton (e.g. the size of the tables, the schema, etc):
        Start at Step 1. 
    
    If you want to generate data based on a given skeleton but with a different underlying
    dependency structure:
        Start at step 3.


----------------------------------------------------------------------------------------------------------------

For this artificial dataset we want to know the ground truth, that is the
local distributions for all attributes. For this artificial dataset to be 
as flexible as possible, we seperated the creation of a skeleton and the 
creation for actual datapoints for all the attributes.

1.  Create a SQLite database schema and save it in 'createSQL_DB.sql'
2.  Run the script 'artificialSkeleton.py' which initializes the database
    and populates it with a skeleton.
    
Now there should be a SQLite database stored in './data/sqlite/artificial.sqlite' that
contains a skeleton. Next we can populate the database with actual datapoints. In general
we are given the data and we want to learn the local distributions (parameter estimation)
and/or the dependency structure (structure learning) from that data.

For the artificial dataset we want to generate data that is sampled from local distributions
defined by us (so that we know the ground truth and are able to e.g. calculate errors, etc).
Since the local distriutions are based on the dependency structure (e.g. they are conditional
probability distributions given the value of the parent attributes), a set of generated datapoints
are associated with a specific dependency structure. 
It follows that the local distributions should also be generated by the depenency strucutre defined
in our PRM specification. After the local distributions have been generated, we can use them to populate
the skeleton with actual datapoint that we know are based on the specified dependency structure (artificialPRM.xml) 
and the generated skeleton (artificialSkeleton.py).

To generate data based on the skeleton:

3.  Create a PRM specification that corresponds to the schema defined before (artificialPRM.xml) 
        Specifically: define the desired dependency structure
4.  Make sure not to define any local distributions in the specifcation
        <LocalDistribution attribute='Aa' file='localDists/Aa.xml'/>
5.  Run the script 'artificialDataset.py' which populates the database associated with the
    PRM specified with actual datapoints sampled from the generated local distributions. These 
    local distributions are also saved on disk.
6.  Adapt the 'artificialPRM.xml' with the local distributions so that they will be loaded (if wished).
    

'''

import sys
import sqlite3


# if the the current folder is a subsub folder or the root Probrem foler, otherwise supply the full path to the 'Probrem/src' folder
sys.path.append("./../../../src")
#sys.path.append("/Users/declerembaul/Documents/Projects/Probrem/src")

import probrem
from ui import config

from analytics import performance
from analytics import visualization

from prm.localdistribution import CPDTabular


import numpy as N


''' SQLite connection '''
database = 'studentprof.10.sqlite'
con = sqlite3.connect('./sqlite/'+database)
con.isolation_level = "DEFERRED"
cur = con.cursor()

# generate a skeleton (if there are already entires in the tables they can be reused)
import createSkeleton

# Loading the PRM in order to define the model parameter. The local distributions are also 
# be used to generate the data
prmSpec = "../model/studentprofPRM.xml"    
config.loadPRM(prmSpec)



# if we have already generated CPDs for the given dependency structure, we can also use those instead of generating new ones
GENERATES_CPDs = False

if GENERATES_CPDs:
    
    print 'GENERATE CPDs'
    def createCPD(attr,cpd):
        
        
        # create CPD
        attr.CPD = CPDTabular(attr)
        # assign cpdMatrix
        attr.CPD.cpdMatrix = cpd
        # calculate cumulative dist
        
        attr.CPD.computeCumulativeDist()
        
        attr.CPD.save(relPath='./localdistributions')
        
    
    exist_funding = N.array( [ [0.8,0.2], [0.4,0.6] ] )
    a = probrem.PRM.attributes['advisor.exist']
    createCPD(a,exist_funding)

    funding_fame = N.array( [ (0.7,0.3), (0.2,0.8) ] )
    a = probrem.PRM.attributes['Professor.funding']
    createCPD(a,funding_fame)

    success_fame = N.array( [ (0.8,0.2), (0.3,0.7) ] )
    a = probrem.PRM.attributes['Student.success']
    createCPD(a,success_fame)
    
    fame = N.array( [ [0.2, 0.8] ] )
    #numpy.atleast_2d
    a = probrem.PRM.attributes['Professor.fame']
    createCPD(a,fame)
    



print 'GENERATE ATTRIBUTE DATA'
for attr in probrem.PRM.topoSortAttributes:

    print attr.name
    
    # all attr objects that we want to generate data for
    if len(attr.parents) == 0:
        attr_pks = ','.join(attr.erClass.pk_string)
        sqlAttr = 'SELECT %s FROM %s GROUP BY %s;'%(attr_pks,attr.erClass.name,attr_pks)
    else:
        
        attr_pks = ','.join(attr.erClass.pk_string)

        #Using the slotchain(s) for the dependency(ies) of the given the given attribute we can construct the string list of tables        
        query_parents = []
        query_tables = [attr.erClass]
        scWhere = []
        for dep in attr.dependenciesChild:
            #SELECT clause
            
            if dep.aggregator is None:
                query_parents.append(dep.parent.fullname)
            else: 
                query_parents.append('ROUND(%s( %s))'%(dep.aggregator('SQLite'),dep.parent.fullname))
                            
            '''
            if dep.aggregator is None:
                #no Aggregation, use parent value directly
                query_parents.append(dep.parent.fullname)
            else:                
                aggr_string = dep.aggregator('SQLite')
                aggr_attr_name = '%s(%s)'%(aggr_string,dep.parent.fullname)
                query_parents.append(aggr_attr_name)
            '''    
            #FROM clause
            for er in dep.slotchain:
                if er not in query_tables:
                    query_tables.append(er)
        
        
            #WHERE clause
            scWhere.extend(dep.slotchain_attr_string)  
            
        sqlParents = ','.join(query_parents)
        
        sqlTables = ",".join([er.name for er in query_tables])    
        sqlWhere = " AND ".join(scWhere)
        
        if len(sqlWhere)!=0:
            sqlWhere = " AND ".join(scWhere)
            sqlAttr = 'SELECT %s,%s FROM %s WHERE %s GROUP BY %s;'%(attr_pks,sqlParents,sqlTables ,sqlWhere,attr_pks)
        else:
            sqlAttr = 'SELECT %s,%s FROM %s GROUP BY %s;'%(attr_pks,sqlParents,sqlTables ,attr_pks)

    
    
    print sqlAttr
        
    cur.execute(sqlAttr)
    sqlUpdates = []
    
    for row in cur:
        #sampling an value for the attribute
        print 'row',row
        attr_pk = None
        if len(attr.parents) == 0:
            attr_pk = row
            attrVal = attr.CPD.sample([])
        else:
            ident = len(attr.erClass.pk) #+len(attr.parents)
            attr_pk = row[0:ident]
            parents_val = row[ident:]
            print 'attr_pk',attr_pk
            print 'parents_val',parents_val
            #try:
            attrVal = attr.CPD.sample(parents_val)
            #except:
            #print 'attr_pk: ',attr_pk
            #print 'parents_val: ',parents_val
                
                
        '''
        sql statement to update val

        UPDATE "table_name"
        SET column_1 = [value1], column_2 = [value2]
        WHERE {condition}
        '''
        
        #update query
        sqlWhere = ' AND '.join(['%s=%s'%(pk_i,obj_i) for (pk_i,obj_i) in zip(attr.erClass.pk_string,attr_pk)])
        
        
        sqlUpdate = 'UPDATE %s SET %s=%s WHERE %s;'%(attr.erClass.name,attr.name,attrVal,sqlWhere)
        sqlUpdates.append(sqlUpdate)
     
    for sqlUpdate in sqlUpdates:
        cur.execute(sqlUpdate) 

    con.commit()        












