<?php
// ///////////////////////////////////////////////////
// Copyright(c) 2021,jiujie
// 日 期：2025/8/13
// 作　者：卢晓峰
// E-mail :51372539@qq.com
// 文件名 :GeneralFunction.php
// 创建时间:09:51
// 编 码：UTF-8
// 摘 要:通用方法调用,主要涉及一些采集需要频繁使用的高频方法
// ///////////////////////////////////////////////////

namespace app\common\server\spider;

use app\common\enum\SpiderEnum;
use GuzzleHttp\Client;
use think\console\Output;

class GeneralFunction{
    /**
     * 单例HTTP客户端
     */
    private static $httpClient = null;

    /**
     * @notes 获取全局HTTP客户端实例
     * @return Client
     */
    public static function getHttpClient(): Client
    {
        if (self::$httpClient === null) {
            self::$httpClient = new Client([
                'timeout'         => 15,          // 总超时15秒
                'connect_timeout' => 10,          // 连接超时10秒（包含DNS解析）
                'retry'           => 3,           // 自动重试3次
                'headers'         => [
                    'User-Agent' => SpiderEnum::getRandomUserAgent(),
                    // 不设置Accept-Encoding，让CURLOPT_ENCODING控制
                ],
                'verify'          => false,       // 忽略SSL证书验证
                'http_errors'     => false,       // 不自动抛出HTTP错误
                'decode_content'  => false,       // 禁用自动解码，避免编码冲突
                'curl'            => [
                    CURLOPT_ENCODING => '',       // 全局禁用所有编码处理
                ]
            ]);
        }
        return self::$httpClient;
    }


    /**
     * @throws \Exception
     * @notes 统一输出消息处理
     * @param Output|null $output 输出对象
     * @param string $message 消息内容（可包含样式标签）
     * @return void
     *
     */
    public static function outputMessage($output, $message)
    {
        if ($output && method_exists($output, 'writeln')) {
            $output->writeln($message);
        } else {
            // 兜底使用echo，移除样式标签
            $cleanMessage = preg_replace('/<[^>]*>/', '', $message);
            echo $cleanMessage;
        }
    }

    /**
     * @throws \Exception
     * @notes 随机IP生成函数 - 动态生成合规的公网IP段
     * @return string 随机IP地址
     */
    public static function generateRandomIP()
    {
        // 动态生成合规的公网IP段，避免写死
        $ip_types = [
            'telecom' => [
                'prefixes' => [58, 59, 60, 61, 116, 117, 118, 119, 120, 121, 122, 123],
                'second_range' => [0, 255],
                'avoid_ranges' => [
                    [10, 0, 0, 0, 10, 255, 255, 255],     // 私有网段
                    [172, 16, 0, 0, 172, 31, 255, 255],   // 私有网段
                    [192, 168, 0, 0, 192, 168, 255, 255], // 私有网段
                    [127, 0, 0, 0, 127, 255, 255, 255],   // 回环地址
                    [224, 0, 0, 0, 255, 255, 255, 255],   // 组播地址
                ]
            ],
            'unicom' => [
                'prefixes' => [110, 111, 112, 113, 114, 115, 124, 125, 126, 140, 141, 142],
                'second_range' => [0, 255],
            ],
            'mobile' => [
                'prefixes' => [39, 111, 112, 120, 121, 183, 202, 203, 218, 219, 220, 221],
                'second_range' => [0, 255],
            ]
        ];

        // 随机选择运营商类型
        $provider = array_rand($ip_types);
        $config = $ip_types[$provider];

        $max_attempts = 20; // 最大尝试次数，避免无限循环
        $attempts = 0;

        do {
            $attempts++;
            // 随机生成IP各段
            $first = $config['prefixes'][array_rand($config['prefixes'])];
            $second = rand($config['second_range'][0], $config['second_range'][1]);
            $third = rand(1, 254);  // 避免0和255
            $fourth = rand(1, 254); // 避免0和255

            $ip = "$first.$second.$third.$fourth";
            $ip_long = ip2long($ip);

            // 检查是否为有效IP
            if ($ip_long === false) {
                continue;
            }

            // 检查是否在避免的范围内
            $is_valid = true;
            if (isset($config['avoid_ranges'])) {
                foreach ($config['avoid_ranges'] as $range) {
                    $range_start = ip2long("{$range[0]}.{$range[1]}.{$range[2]}.{$range[3]}");
                    $range_end = ip2long("{$range[4]}.{$range[5]}.{$range[6]}.{$range[7]}");

                    if ($ip_long >= $range_start && $ip_long <= $range_end) {
                        $is_valid = false;
                        break;
                    }
                }
            }

            // 额外检查：确保不是特殊用途IP
            if ($is_valid) {
                // 避免0.x.x.x, 255.x.x.x
                if ($first == 0 || $first == 255) {
                    $is_valid = false;
                }

                // 避免以0或255结尾的网段
                if ($second == 0 || $second == 255) {
                    if (rand(0, 3) == 0) { // 25%概率跳过，增加随机性
                        $is_valid = false;
                    }
                }
            }

            if ($is_valid) {
                return $ip;
            }

        } while ($attempts < $max_attempts);

        // 如果尝试多次仍未生成有效IP，使用备用方案
        $backup_ranges = [
            ['14.0.0.0', '14.255.255.255'],
            ['27.0.0.0', '27.255.255.255'],
            ['36.0.0.0', '36.255.255.255'],
            ['49.0.0.0', '49.255.255.255'],
        ];

        $range = $backup_ranges[array_rand($backup_ranges)];
        $start_ip = ip2long($range[0]);
        $end_ip = ip2long($range[1]);

        return long2ip(rand($start_ip, $end_ip));
    }


    /**
     * @throws \Exception
     * @notes HTTP头池 - 随机化请求头
     * @return array 随机请求头
     */
    public static function getRandomHeaders()
    {
        $headers = SpiderEnum::BASE_HEADERS;

        // 随机选择添加可选头
        if (rand(0, 1)) {
            $headers = array_merge($headers, SpiderEnum::OPTIONAL_HEADERS);
        }

        return $headers;
    }

    /**
     * @throws \Exception
     * @notes 生成随机手机号
     * @return string 手机号
     *
     */
    public static function generateRandomPhone()
    {
        $prefixes = ['130', '131', '132', '133', '134', '135', '136', '137', '138', '139',
            '150', '151', '152', '153', '155', '156', '157', '158', '159',
            '170', '171', '173', '175', '176', '177', '178',
            '180', '181', '182', '183', '184', '185', '186', '187', '188', '189'];

        $prefix = $prefixes[array_rand($prefixes)];
        $suffix = str_pad(rand(0, 99999999), 8, '0', STR_PAD_LEFT);

        return $prefix . $suffix;
    }

    /**
     * @throws \Exception
     * @notes 生成13位时间戳
     * @return int 毫秒时间戳
     *
     */
    public static function getTimestamp()
    {
        $timestamp = microtime(true);
        return (int)($timestamp * 1000);
    }

    /**
     * @throws \Exception
     * @notes 格式化日期 - 通用日期格式化函数
     * @param string $dateStr 日期字符串
     * @param string $format 输出格式，默认Y-m-d
     * @return string|null 格式化后的日期
     *
     */
    public static function formatDate($dateStr, $format = 'Y-m-d')
    {
        if (empty($dateStr)) {
            return null;
        }

        try {
            $timestamp = strtotime($dateStr);
            if ($timestamp) {
                return date($format, $timestamp);
            }
        } catch (\Exception $e) {
            // 忽略日期解析错误
        }

        return null;
    }

    /**
     * @throws \Exception
     * @notes 生成随机IP头信息 - 用于防封策略
     * @return array 随机IP头信息
     *
     */
    public static function getRandomIPHeaders()
    {
        $ip1 = self::generateRandomIP();
        $ip2 = self::generateRandomIP();
        $ip3 = self::generateRandomIP();

        return [
            'X-Forwarded-For' => "$ip1, $ip2, $ip3",
            'X-Real-IP' => $ip1,
            'X-Client-IP' => $ip2,
            'X-Originating-IP' => $ip3,
            'Client-IP' => $ip1,
        ];
    }

    /**
     * @throws \Exception
     * @notes 随机延时函数 - 控制采集频率
     * @param int $min_ms 最小毫秒数
     * @param int $max_ms 最大毫秒数
     * @param Output|null $output 输出对象
     * @return void
     *
     */
    public static function randomDelay($min_ms, $max_ms, $output = null)
    {
        $delay_ms = rand($min_ms, $max_ms); // 毫秒数
        $delay_seconds = round($delay_ms / 1000, 3); // 转换为秒，保留3位小数

        // 输出延迟时间信息
        if ($output) {
            self::outputMessage($output, "<comment>[GeneralFunction] 延迟时间: {$delay_ms}ms ({$delay_seconds}s)</comment>");
        }

        $delay = $delay_ms * 1000; // 转换为微秒
        usleep($delay);
    }

    /**
     * @throws \Exception
     * @notes 通用HTTP请求封装 - 带防封策略
     * @param string $url 请求URL
     * @param array $options 请求选项
     * @return string 响应内容
     *
     */
    public static function httpRequest($url, $options = [])
    {
        // 默认配置
        $defaultOptions = [
            'timeout' => 10,
            'verify' => false,
            'headers' => [],
            'cookies' => '',
            'use_random_ip' => true,
            'user_agent' => '',
        ];

        $options = array_merge($defaultOptions, $options);

        $client = new \GuzzleHttp\Client([
            'timeout' => $options['timeout'],
            'verify' => $options['verify'],
        ]);

        // 构建请求头
        $headers = $options['headers'];
        
        // 添加User-Agent
        if (empty($options['user_agent'])) {
            $headers['User-Agent'] = SpiderEnum::getUserAgent()[array_rand(SpiderEnum::getUserAgent())];
        } else {
            $headers['User-Agent'] = $options['user_agent'];
        }

        // 添加Cookie
        if (!empty($options['cookies'])) {
            $headers['Cookie'] = $options['cookies'];
        }

        // 添加随机IP头
        if ($options['use_random_ip']) {
            $ipHeaders = self::getRandomIPHeaders();
            $headers = array_merge($headers, $ipHeaders);
        }

        // 合并通用头信息
        $headers = array_merge(self::getRandomHeaders(), $headers);

        $response = $client->request('GET', $url, [
            'headers' => $headers
        ]);

        return $response->getBody()->getContents();
    }

    /**
     * @throws \Exception
     * @notes 通用存在性检查 - 检查数据库中记录是否存在
     * @param string $model 模型类名
     * @param string $field 字段名
     * @param mixed $value 字段值
     * @return bool 是否存在
     *
     */
    public static function checkExists($model, $field, $value)
    {
        if (empty($value)) {
            return false;
        }

        // 使用模型查询
        $exists = $model::where($field, $value)->find();

        return !empty($exists);
    }

    /**
     * @throws \Exception
     * @notes 安全获取数组嵌套值 - 避免undefined index错误
     * @param array $array 目标数组
     * @param string $path 路径，如 'data.user.name'
     * @param mixed $default 默认值
     * @return mixed 获取到的值或默认值
     *
     */
    public static function getNestedValue($array, $path, $default = null)
    {
        $keys = explode('.', $path);
        $current = $array;

        foreach ($keys as $key) {
            if (!is_array($current) || !isset($current[$key])) {
                return $default;
            }
            $current = $current[$key];
        }

        return $current;
    }


    /**
     * @throws \Exception
     * @notes 生成随机延时范围 - 用于控制采集频率
     * @param int $baseMs 基础毫秒数
     * @param float $variance 变化幅度（0-1）
     * @return array [min_ms, max_ms]
     *
     */
    public static function getRandomDelayRange($baseMs, $variance = 0.5)
    {
        $minMs = intval($baseMs * (1 - $variance));
        $maxMs = intval($baseMs * (1 + $variance));
        
        return [$minMs, $maxMs];
    }

}