from collections import OrderedDict, defaultdict
import json
import time

from p4pktgen.config import Config
from p4pktgen.core.translator import TestPathResult
from p4pktgen.util.graph import GraphVisitor
from p4pktgen.util.statistics import Statistics


class PathCoverageGraphVisitor(GraphVisitor):
    def __init__(self, translator, parser_path, source_info_to_node_name,
                 results, test_case_writer):
        super(PathCoverageGraphVisitor, self).__init__()
        self.translator = translator
        self.parser_path = parser_path
        self.source_info_to_node_name = source_info_to_node_name
        self.path_count = 0
        self.results = results
        self.test_case_writer = test_case_writer
        self.stats_per_traversal = defaultdict(int)

    def preprocess_edges(self, neighbors):
        return neighbors

    def visit(self, control_path, is_complete_control_path):
        self.path_count += 1
        self.translator.push()
        expected_path, result, test_case, packet_lst = \
            self.translator.generate_constraints(
                self.parser_path, control_path,
                self.source_info_to_node_name, self.path_count, is_complete_control_path)

        if result == TestPathResult.SUCCESS and is_complete_control_path:
            Statistics().avg_full_path_len.record(
                len(self.parser_path + control_path))
        if result == TestPathResult.NO_PACKET_FOUND:
            Statistics().avg_unsat_path_len.record(
                len(self.parser_path + control_path))
            Statistics().count_unsat_paths.inc()

        if Config().get_record_statistics():
            Statistics().record(result, is_complete_control_path, self.translator)

        record_result = (is_complete_control_path
                         or (result != TestPathResult.SUCCESS))
        if record_result:
            # Doing file writing here enables getting at least
            # some test case output data for p4pktgen runs that
            # the user kills before it completes, e.g. because it
            # takes too long to complete.
            self.test_case_writer.write(test_case, packet_lst)
            result_path = [n.src for n in self.parser_path
                           ] + ['sink'] + [(n.src, n) for n in control_path]
            result_path_tuple = tuple(expected_path)
            if result_path_tuple in self.results and self.results[result_path_tuple] != result:
                logging.error("result_path %s with result %s"
                              " is already recorded in results"
                              " while trying to record different result %s"
                              "" % (result_path,
                                    self.results[result_path_tuple], result))
                assert False
            self.results[tuple(result_path)] = result
            if result == TestPathResult.SUCCESS and is_complete_control_path:
                for x in control_path:
                    Statistics().stats_per_control_path_edge[x] += 1
                now = time.time()
                # Use real time to avoid printing these details
                # too often in the output log.
                if now - Statistics(
                ).last_time_printed_stats_per_control_path_edge >= 30:
                    Statistics().log_control_path_stats(
                        Statistics().stats_per_control_path_edge,
                        Statistics().num_control_path_edges)
                    Statistics(
                    ).last_time_printed_stats_per_control_path_edge = now
            Statistics().stats[result] += 1
            self.stats_per_traversal[result] += 1

        tmp_num = Config().get_max_paths_per_parser_path()
        if (tmp_num
                and stats_per_traversal[TestPathResult.SUCCESS] >= tmp_num):
            logging.info("Already found %d packets for parser path %d of %d."
                         "  Backing off so we can get to next parser path ASAP"
                         "" % (stats_per_traversal[TestPathResult.SUCCESS],
                               parser_path_num, len(parser_paths)))
            go_deeper = False
        else:
            go_deeper = (result == TestPathResult.SUCCESS)
        return go_deeper

    def backtrack(self):
        self.translator.pop()
