"""
Database models for the TestSuite databases themselves.

These are a bit magical because the models themselves are driven by the test
suite metadata, so we only create the classes at runtime.
"""

import datetime
import json

import sqlalchemy
from sqlalchemy import *

import testsuite

class TestSuiteDB(object):
    """
    Wrapper object for an individual test suites database tables.

    This wrapper is somewhat special in that it handles specializing the
    metatable instances for the given test suite.

    Clients are expected to only access the test suite database tables by going
    through the model classes constructed by this wrapper object.
    """

    def __init__(self, v4db, test_suite):
        testsuitedb = self
        self.v4db = v4db
        self.test_suite = test_suite

        # Save caches of the various fields.
        self.machine_fields = list(self.test_suite.machine_fields)
        self.order_fields = list(self.test_suite.order_fields)
        self.run_fields = list(self.test_suite.run_fields)
        self.sample_fields = list(self.test_suite.sample_fields)

        self.base = sqlalchemy.ext.declarative.declarative_base()

        # Create parameterized model classes for this test suite.
        db_key_name = self.test_suite.db_key_name
        class Machine(self.base):
            __tablename__ = db_key_name + '_Machine'

            id = Column("ID", Integer, primary_key=True)
            name = Column("Name", String(256), index=True)

            # The parameters blob is used to store any additional information
            # reported by the run but not promoted into the machine record. Such
            # data is stored as a JSON encoded blob.
            parameters = Column("Parameters", Binary)

            # Dynamically create fields for all of the test suite defined
            # machine fields.
            class_dict = locals()
            for item in self.machine_fields:
                if item.name in class_dict:
                    raise ValueError,"test suite defines reserved key %r" % (
                        name,)

                class_dict[item.name] = item.column = Column(
                    item.name, String(256))

            def __init__(self, name):
                self.name = name

            def __repr__(self):
                return '%s_%s%r' % (db_key_name, self.__class__.__name__,
                                    (self.name,))

        class Order(self.base):
            __tablename__ = db_key_name + '_Order'

            id = Column("ID", Integer, primary_key=True)

            # Dynamically create fields for all of the test suite defined order
            # fields.
            #
            # FIXME: We are probably going to want to index on some of these,
            # but need a bit for that in the test suite definition.
            class_dict = locals()
            for item in self.order_fields:
                if item.name in class_dict:
                    raise ValueError,"test suite defines reserved key %r" % (
                        name,)

                class_dict[item.name] = item.column = Column(
                    item.name, String(256))

            def __init__(self):
                pass

            def __repr__(self):
                return '%s_%s%r' % (db_key_name, self.__class__.__name__,
                                    ())

        class Run(self.base):
            __tablename__ = db_key_name + '_Run'

            id = Column("ID", Integer, primary_key=True)
            machine_id = Column("MachineID", Integer, ForeignKey(Machine.id),
                                index=True)
            order_id = Column("OrderID", Integer, ForeignKey(Order.id),
                              index=True)
            imported_from = Column("ImportedFrom", String(512))
            start_time = Column("StartTime", DateTime)
            end_time = Column("EndTime", DateTime)

            # The parameters blob is used to store any additional information
            # reported by the run but not promoted into the machine record. Such
            # data is stored as a JSON encoded blob.
            parameters = Column("Parameters", Binary)

            machine = sqlalchemy.orm.relation(Machine)
            order = sqlalchemy.orm.relation(Order)

            # Dynamically create fields for all of the test suite defined run
            # fields.
            #
            # FIXME: We are probably going to want to index on some of these,
            # but need a bit for that in the test suite definition.
            class_dict = locals()
            for item in self.run_fields:
                if item.name in class_dict:
                    raise ValueError,"test suite defines reserved key %r" % (
                        name,)

                class_dict[item.name] = item.column = Column(
                    item.name, String(256))

            def __init__(self, machine, order, start_time, end_time):
                self.machine = machine
                self.order = order
                self.start_time = start_time
                self.end_time = end_time
                self.imported_from = None

            def __repr__(self):
                return '%s_%s%r' % (db_key_name, self.__class__.__name__,
                                    (self.machine, self.order, self.start_time,
                                     self.end_time))

        class Test(self.base):
            __tablename__ = db_key_name + '_Test'

            id = Column("ID", Integer, primary_key=True)
            name = Column("Name", String(256), unique=True, index=True)

            def __init__(self, name):
                self.name = name

            def __repr__(self):
                return '%s_%s%r' % (db_key_name, self.__class__.__name__,
                                    (self.name,))

        class Sample(self.base):
            __tablename__ = db_key_name + '_Sample'

            id = Column("ID", Integer, primary_key=True)
            # We do not need an index on run_id, this is covered by the compound
            # (Run(ID),Test(ID)) index we create below.
            run_id = Column("RunID", Integer, ForeignKey(Run.id))
            test_id = Column("TestID", Integer, ForeignKey(Test.id), index=True)

            run = sqlalchemy.orm.relation(Run)
            test = sqlalchemy.orm.relation(Test)

            # Dynamically create fields for all of the test suite defined sample
            # fields.
            #
            # FIXME: We might want to index some of these, but for a different
            # reason than above. It is possible worth it to turn the compound
            # index below into a covering index. We should evaluate this once
            # the new UI is up.
            class_dict = locals()
            for item in self.sample_fields:
                if item.name in class_dict:
                    raise ValueError,"test suite defines reserved key %r" % (
                        name,)

                if item.type.name == 'Real':
                    item.column = Column(item.name, Float)
                elif item.type.name == 'Status':
                    item.column = Column(item.name, Integer, ForeignKey(
                            testsuite.StatusKind.id))
                else:
                    raise ValueError,(
                        "test suite defines unknown sample type %r" (
                            item.type.name,))

                class_dict[item.name] = item.column

            def __init__(self, run, test, **kwargs):
                self.run = run
                self.test = test

                # Initialize sample fields (defaulting to 0, for now).
                for item in testsuitedb.sample_fields:
                    setattr(self, item.name, kwargs.get(item.name, 0))

            def __repr__(self):
                fields = dict((item.name, getattr(self, item.name))
                              for item in self.sample_fields)

                return '%s_%s(%r, %r, **%r)' % (
                    db_key_name, self.__class__.__name__,
                    self.run, self.test, fields)

        self.Machine = Machine
        self.Run = Run
        self.Test = Test
        self.Sample = Sample
        self.Order = Order

        # Create the compound index we cannot declare inline.
        sqlalchemy.schema.Index("ix_%s_Sample_RunID_TestID" % db_key_name,
                                Sample.run_id, Sample.test_id)

        # Create the index we use to ensure machine uniqueness.
        args = [Machine.name, Machine.parameters]
        for item in self.machine_fields:
            args.append(item.column)
        sqlalchemy.schema.Index("ix_%s_Machine_Unique" % db_key_name,
                                *args, unique = True)

        # Create the test suite database tables in case this is a new database.
        self.base.metadata.create_all(self.v4db.engine)

        # Add several shortcut aliases, similar to the ones on the v4db.
        self.add = self.v4db.add
        self.commit = self.v4db.commit
        self.query = self.v4db.query
        self.rollback = self.v4db.rollback

    def _getOrCreateMachine(self, machine_data):
        """
        _getOrCreateMachine(data) -> Machine, bool

        Add or create (and insert) a Machine record from the given machine data
        (as recorded by the test interchange format).

        The boolean result indicates whether the returned record was constructed
        or not.
        """

        # Convert the machine data into a machine record. We construct the query
        # to look for any existing machine at the same time as we build up the
        # record to possibly add.
        #
        # FIXME: This feels inelegant, can't SA help us out here?
        query = self.query(self.Machine).\
            filter(self.Machine.name == machine_data['Name'])
        machine = self.Machine(machine_data['Name'])
        machine_parameters = machine_data['Info'].copy()

        # First, extract all of the specified machine fields.
        for item in self.machine_fields:
            if item.info_key in machine_parameters:
                value = machine_parameters.pop(item.info_key)
            else:
                # For now, insert empty values for any missing fields. We don't
                # want to insert NULLs, so we should probably allow the test
                # suite to define defaults.
                value = ''

            # FIXME: Avoid setattr.
            query = query.filter(item.column == value)
            setattr(machine, item.name, value)

        # Convert any remaining machine_parameters into a JSON encoded blob. We
        # encode this as an array to avoid a potential ambiguity on the key
        # ordering.
        machine.parameters = json.dumps(sorted(machine_parameters.items()))
        query = query.filter(self.Machine.parameters == machine.parameters)

        # Execute the query to see if we already have this machine.
        try:
            return query.one(),False
        except sqlalchemy.orm.exc.NoResultFound:
            # If not, add the machine.
            self.add(machine)

            return machine,True

    def _getOrCreateOrder(self, run_parameters):
        """
        _getOrCreateOrder(data) -> Order, bool

        Add or create (and insert) an Order record based on the given run
        parameters (as recorded by the test interchange format).

        The run parameters that define the order will be removed from the
        provided ddata argument.

        The boolean result indicates whether the returned record was constructed
        or not.
        """

        query = self.query(self.Order)
        order = self.Order()

        # First, extract all of the specified order fields.
        for item in self.order_fields:
            if item.info_key in run_parameters:
                value = run_parameters.pop(item.info_key)
            else:
                # We require that all of the order fields be present.
                raise ValueError,"""\
supplied run is missing required run parameter: %r""" % (
                    item.info_key)

            # FIXME: Avoid setattr.
            query = query.filter(item.column == value)
            setattr(order, item.name, value)

        # Execute the query to see if we already have this order.
        try:
            return query.one(),False
        except sqlalchemy.orm.exc.NoResultFound:
            # If not, add the run.
            self.add(order)

            return order,True

    def _getOrCreateRun(self, run_data, machine):
        """
        _getOrCreateRun(data) -> Run, bool

        Add a new Run record from the given data (as recorded by the test
        interchange format).

        The boolean result indicates whether the returned record was constructed
        or not.
        """

        # Extra the run parameters that define the order.
        run_parameters = run_data['Info'].copy()

        # The tag has already been used to dispatch to the appropriate database.
        run_parameters.pop('tag')

        # Find the order record.
        order,inserted = self._getOrCreateOrder(run_parameters)
        start_time = datetime.datetime.strptime(run_data['Start Time'],
                                                "%Y-%m-%d %H:%M:%S")
        end_time = datetime.datetime.strptime(run_data['End Time'],
                                              "%Y-%m-%d %H:%M:%S")

        # Convert the rundata into a run record. As with Machines, we construct
        # the query to look for any existingrun at the same time as we build up
        # the record to possibly add.
        #
        # FIXME: This feels inelegant, can't SA help us out here?
        query = self.query(self.Run).\
            filter(self.Run.machine_id == machine.id).\
            filter(self.Run.order_id == order.id).\
            filter(self.Run.start_time == start_time).\
            filter(self.Run.end_time == end_time)
        run = self.Run(machine, order, start_time, end_time)

        # First, extract all of the specified run fields.
        for item in self.run_fields:
            if item.info_key in run_parameters:
                value = run_parameters.pop(item.info_key)
            else:
                # For now, insert empty values for any missing fields. We don't
                # want to insert NULLs, so we should probably allow the test
                # suite to define defaults.
                value = ''

            # FIXME: Avoid setattr.
            query = query.filter(item.column == value)
            setattr(run, item.name, value)

        # Any remaining parameters are saved as a JSON encoded array.
        run.parameters = json.dumps(sorted(run_parameters.items()))
        query = query.filter(self.Run.parameters == run.parameters)

        # Execute the query to see if we already have this run.
        try:
            return query.one(),False
        except sqlalchemy.orm.exc.NoResultFound:
            # If not, add the run.
            self.add(run)

            return run,True

    def _importSampleValues(self, tests_data, run):
        # We now need to transform the old schema data (composite samples split
        # into multiple tests) into the V4DB format where each sample is a
        # complete record.

        # Load a map of all the tests, which we will extend when we find tests
        # that need to be added.
        test_cache = dict((test.name, test)
                          for test in self.query(self.Test))

        # We build a map of test name to sample values, by scanning all the
        # tests. This is complicated by the interchange's support of multiple
        # values, which we cannot properly aggregate. We handle this by keying
        # off of the test name and the sample index.
        #
        # Note that the above strategy only works if reports don't report the
        # same test name multiple times. That was possible in the schema, but I
        # believe never used.
        sample_records = {}
        for test_data in tests_data:
            if test_data['Info']:
                raise ValueError,"""\
test parameter sets are not supported by V4DB databases"""

            name = test_data['Name']

            # Map this reported test name into a test name and a sample field.
            #
            # FIXME: This is really slow.
            for item in self.sample_fields:
                if name.endswith(item.info_key):
                    test_name = name[:-len(item.info_key)]
                    sample_field = item
                    break
            else:
                # Disallow tests which do not map to a sample field.
                raise ValueError,"""\
test %r does not map to a sample field in the reported suite""" % (
                    name)

            # Get or create the test.
            test = test_cache.get(test_name)
            if test is None:
                test_cache[test_name] = test = self.Test(test_name)
                self.add(test)

            for i,value in enumerate(test_data['Data']):
                record_key = (test_name, i)
                record = sample_records.get(record_key)
                if record is None:
                    sample_records[record_key] = sample = self.Sample(run, test)
                    self.add(sample)

                # FIXME: Avoid setattr.
                setattr(sample, sample_field.name, value)

    def importDataFromDict(self, data):
        """
        importDataFromDict(data) -> Run, bool

        Import a new run from the provided test interchange data, and return the
        constructed Run record.

        The boolean result indicates whether the returned record was constructed
        or not (i.e., whether the data was a duplicate submission).
        """

        # Construct the machine entry.
        machine,inserted = self._getOrCreateMachine(data['Machine'])

        # Construct the run entry.
        run,inserted = self._getOrCreateRun(data['Run'], machine)

        # If we didn't construct a new run, this is a duplicate
        # submission. Return the prior Run.
        if not inserted:
            return False, run

        self._importSampleValues(data['Tests'], run)

        return True, run
