'''
MongoDB is a non-relational database used to store feature values.
It stores data in JSON format, with a hierarchy of
db server -> database -> collection -> record.

The record looks like this:
static document
{
    "data_source": "Changgung",
    "scan": "baihanxiang_20190211",
    "atlas": "brodmann_lrce",
    "feature": "BOLD.inter.BC",
    "dynamic": 0,
    "value": "...actual csv str...",
    "comment": {"...descriptive str..."}
}

dynamic document
{
    "data_source":"Changgung",
    "scan": "CMSA_01",
    "atlas": "brodmann_lrce",
    "feature": "BOLD.inter.BC",
    "dynamic": 1, 
    "window_length": 22,
    "step_size": 1,
    "slice_num": the num of the slice 0,1,2,3…
    "value": "...actual csv str...",
    "comment": {"...descriptive str..."}
}
'''

import pymongo
import pickle
from mmdps.proc import atlas, netattr


class MongoDBDatabase:
    """
    docstring for MongoDBDatabase
    parameter data_source: 	the only non-default parameter of constructor function
    parameter scan :		mriscan 
    parameter atlas_name : 	name of atlas
    parameter feature : 	name of feature file
    parameter dynamic : 	0/1
    parameter window_length : window_length
    parameter step_size : 	step_size
    parameter slice_num : 	the number of slice in a sequence
    parameter comment: 		default {}
    """

    def __init__(self, data_source, host='localhost', port=27017, col='features', password=''):
        """
        use data_source as the name of database
        default collection : 'features'
        """
        self.data_source = data_source
        self.client = pymongo.MongoClient(host, port)
        self.db = self.client[data_source]
        self.col = self.db[col]
        self.temp_collection = self.db['Temp-features']

    def generate_static_query(self, scan, atlas_name, feature, comment_dict={}):
        static_query = dict(data_source=self.data_source, scan=scan,
                            atlas=atlas_name, feature=feature, dynamic=0, comment=comment_dict)
        return static_query

    def genarate_dynamic_query(self, scan, atlas_name, feature, window_length, step_size, comment_dict={}):
        dynamic_query = dict(data_source=self.data_source, scan=scan, atlas=atlas_name, feature=feature,
                             dynamic=1, window_length=window_length, step_size=step_size, comment=comment_dict)
        return dynamic_query

    def query_static(self, scan, atlas_name, feature, comment_dict={}):
        static_query = self.generate_static_query(
            scan, atlas_name, feature, comment_dict)
        self.col = self.db['features']
        return self.col.find(static_query)

    def query_dynamic(self, scan, atlas_name, feature, window_length, step_size, comment_dict={}):
        dynamic_query = self.genarate_dynamic_query(
            scan, atlas_name, feature, window_length, step_size, comment_dict)
        self.col = self.db['dynamic_data']
        return self.col.find(dynamic_query).sort("slice_num", 1)

    def exist_static(self, scan, atlas_name, feature, comment_dict={}):
        self.col = self.db['features']
        return self.col.count_documents(self.generate_static_query(scan, atlas_name, feature, comment_dict))

    def exist_dynamic(self, scan, atlas_name, feature, window_length, step_size, comment_dict={}):
        self.col = self.db['dynamic_data']
        return self.col.count_documents(self.genarate_dynamic_query(scan, atlas_name, feature, window_length, step_size, comment_dict))

    def generate_static_document(self, scan, atlas_name, feature, value, comment_dict={}):
        static_document = dict(data_source=self.data_source, scan=scan, atlas=atlas_name,
                               feature=feature, dynamic=0, value=value, comment=comment_dict)
        return static_document

    def generate_dynamic_document(self, scan, atlas_name, feature, window_length, step_size, slice_num, value, comment_dict={}):
        dynamic_document = dict(data_source=self.data_source, scan=scan, atlas=atlas_name, feature=feature, dynamic=1,
                                window_length=window_length, step_size=step_size, slice_num=slice_num, value=value, comment=comment_dict)
        return dynamic_document

    def save_static_feature(self, feature, comment_dict={}):
        """
        feature could be netattr.Net or netattr.Attr
        comment_dict correspond to document['comment']
        """
        if self.exist_static(feature.scan, feature.atlasobj.name, feature.feature_name):
            raise MultipleRecordException(feature.scan, 'Please check again.')
        attrdata = pickle.dumps(feature.data)
        self.col = self.db['features']
        document = self.generate_static_document(
            feature.scan, feature.atlasobj.name, feature.feature_name, attrdata, comment_dict)
        self.col.insert_one(document)

    def remove_static_feature(self, scan, atlas_name, feature):
        self.col = self.db['features']
        query = self.generate_static_query(scan, atlas_name, feature)
        self.col.find_one_and_delete(query)

    def save_dynamic_attr(self, attr, comment_dict={}):
        """
        attr is a netattr.DynamicAttr instance
        """
        if self.exist_dynamic(attr.scan, attr.atlasobj.name, attr.feature_name, attr.window_length, attr.step_size):
            raise MultipleRecordException(attr.scan, 'Please check again.')
        self.col = self.db['dynamic_data']
        for i in range(attr.data.shape[1]):
            # i is the num of the column in data matrix
            value = pickle.dumps(attr.data[:, i])
            slice_num = i
            document = self.generate_dynamic_document(
                attr.scan, attr.atlasobj.name, attr.feature_name, attr.window_length, attr.step_size, slice_num, value, comment_dict)
            self.col.insert_one(document)

    def remove_dynamic_attr(self, scan, feature, window_length, step_size, atlas_name='brodmann_lrce'):
        """
        fiter and delete all the slice in dynamic_attr
        default atlas is brodmann_lrce
        """
        self.col = self.db['dynamic_data']
        query = self.genarate_dynamic_query(
            scan, atlas_name, feature, window_length, step_size)
        self.col.delete_many(query)

    def save_dynamic_network(self, net, comment_dict={}):
        """
        net is netattr.DynamicNet
        """
        if self.exist_dynamic(net.scan, net.atlasobj.name, net.feature_name, net.window_length, net.step_size):
            raise MultipleRecordException(net.scan, 'Please check again.')
        self.col = self.db['dynamic_data']
        for i in range(net.data.shape[2]):
            # i is the slice_num of the net
            value = pickle.dumps(net.data[:, :, i])
            slice_num = i
            document = self.generate_dynamic_document(
                net.scan, net.atlasobj.name, net.feature_name, net.window_length, net.step_size, slice_num, value, comment_dict)
            self.col.insert_one(document)

    def remove_dynamic_network(self, scan, window_length, step_size, atlas_name='brodmann_lrce', feature='BOLD.net'):
        """
        fiter and delete all the slice in dynamic_network
        default atlas is bromann_lrce 
        default feature is BOLD.net
        """
        self.col = self.db['dynamic_data']
        query = self.genarate_dynamic_query(
            scan, atlas_name, feature, window_length, step_size)
        self.col.delete_many(query)

    def get_attr(self, scan, atlas_name, feature):
        # return to an attr object  directly
        if self.exist_static(scan, atlas_name, feature):
            binary_data = self.query_static(scan, atlas_name, feature)['value']
            attrdata = pickle.loads(binary_data)
            atlasobj = atlas.get(atlas_name)
            attr = netattr.Attr(attrdata, atlasobj, scan, feature)
            return attr
        else:
            print("can't find the document you look for. scan: %s, atlas: %s, feature: %s." % (
                scan, atlas_name, feature))
            raise NoRecordFoundException(scan)
            return None

    def get_net(self, scan, atlas_name, feature):
        # return to an net object directly
        if self.exist_static(scan, atlas_name, feature):
            binary_data = self.query_static(scan, atlas_name, feature)['value']
            netdata = pickle.loads(binary_data)
            atlasobj = atlas.get(atlas_name)
            net = netattr.Net(netdata, atlasobj, scan, feature)
            return net
        else:
            print("can't find the document you look for. scan: %s, atlas: %s, feature: %s." % (
                scan, atlas_name, feature))
            raise NoRecordFoundException(scan)
            return None

    def put_temp_data(self, temp_data, description_dict, overwrite = False):
        """
        Insert temporary data into MongoDB. 
        Input temp_data as a serializable object (like np.array).
        The description_dict should be a dict whose keys do not contain 'value', which is used to store serialized data
        """
        # check if record already exists, given description_dict
        count = self.temp_collection.count_documents(description_dict)
        if count > 0 and not overwrite:
            raise MultipleRecordException(description_dict, 'Please consider a new name')
        elif count > 0 and overwrite:
            self.temp_collection.delete_many(description_dict)
        description_dict.update(dict(value = pickle.dumps(temp_data)))
        self.temp_collection.insert_one(description_dict)

    def get_temp_data(self, description_dict):
        """
        Get temporary data with description_dict
        Return a dict with value:temp_data (de-serialized)
        """
        result = self.temp_collection.find_one(description_dict)
        result['value'] = pickle.loads(result['value'])
        return result

    def remove_temp_data(self, description_dict = {}):
        """
        Delete all temp records according to description_dict
        If None is input, delete all temp data
        """
        self.temp_collection.delete_many(description_dict)


class MultipleRecordException(Exception):
    """
    """

    def __init__(self, name, suggestion=''):
        super(MultipleRecordException, self).__init__()
        self.name = name
        self.suggestion = suggestion

    def __str__(self):
        return 'Multiple record found for %s. %s' % (self.name, self.suggestion)

    def __repr__(self):
        return 'Multiple record found for %s. %s' % (self.name, self.suggestion)


class NoRecordFoundException(Exception):
    """
    """

    def __init__(self, name, suggestion=''):
        super(NoRecordFoundException, self).__init__()
        self.name = name
        self.suggestion = ''

    def __str__(self):
        return 'No record found for %s. %s' % (self.name, self.suggestion)

    def __repr__(self):
        return 'No record found for %s. %s' % (self.name, self.suggestion)


if __name__ == '__main__':
    pass
