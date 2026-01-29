<?php
/**
 * 百度图片搜索API
 * 解析出带后缀的图片URL
 */

namespace app\common\server\spider;

use app\common\enum\SpiderEnum;
use GuzzleHttp\Exception\ConnectException;
use GuzzleHttp\Exception\RequestException;

class SpiderBaiduImage
{

    private static $base_image_url = 'https://image.baidu.com/';
    private static $base_baidu_url = 'https://www.baidu.com/';
    private static $base_zhidao_url = 'https://zhidao.baidu.com/';
    private static $base_baiker_url = 'https://baike.baidu.com/';
    private static $base_tieba_url = 'https://tieba.baidu.com/';
    private static $base_news_url = 'https://news.baidu.com/';
    private static $base_haokan_url = 'https://haokan.baidu.com/';
    private static $base_pan_url = 'https://haokan.baidu.com/';
    private static $base_wenku_url = 'https://haokan.baidu.com/';

    /**
     * @note 获取随机Referer
     * @param string $keyword 搜索关键词
     * @return string
     */
    private static function getRandomReferer($keyword): string
    {
        // 随机生成分页参数
        $randomPn = rand(0, 100) * 20; // 0, 20, 40, 60, 80, 100... 最大2000
        $searchPn = rand(0, 50) * 10;  // 0, 10, 20, 30... 最大500
        $referrers = [
            // 百度图片首页
            self::$base_image_url,
            // 百度图片搜索页面
            self::$base_image_url . 'search/index?tn=baiduimage&word=' . urlencode($keyword),
            // 百度图片搜索页面（随机分页）
            self::$base_image_url . 'search/index?tn=baiduimage&word=' . urlencode($keyword) . '&pn=' . $randomPn,
            // 百度图片搜索（高级+随机分页）
            self::$base_image_url . 'search/index?tn=baiduimage&word=' . urlencode($keyword) . '&z=0&pn=' . $randomPn,
            // 百度图片搜索（指定尺寸+随机分页）
            self::$base_image_url . 'search/index?tn=baiduimage&word=' . urlencode($keyword) . '&z=3&pn=' . $randomPn,
            // 百度图片搜索（按时间+随机分页）
            self::$base_image_url . 'search/index?tn=baiduimage&word=' . urlencode($keyword) . '&z=0&pn=' . $randomPn . '&rn=30',
            // 百度图片首页高级搜索
            self::$base_image_url . 'search/advanced',
            // 百度主页
            self::$base_baidu_url,
            // 百度搜索结果页
            self::$base_baidu_url . 's?wd=' . urlencode($keyword),
            // 百度搜索（随机分页）
            self::$base_baidu_url . 's?wd=' . urlencode($keyword) . '&pn=' . $searchPn,
            // 百度知道
            self::$base_zhidao_url . 'search?word=' . urlencode($keyword),
            // 百度百科
            self::$base_baiker_url . 'search?word=' . urlencode($keyword),
            // 百度贴吧
            self::$base_tieba_url . 'f?kw=' . urlencode($keyword),
            // 百度新闻
            self::$base_news_url . 'ns?word=' . urlencode($keyword),
            //百度视频
            self::$base_haokan_url . '?sfrom=baidu-top&t=' . time() . '&r=' . rand(1000, 9999),
            //百度网盘
            self::$base_pan_url . '?from=' . rand(1000000, 9999999) . 'h&ts=' . time(),
           //百度文库
            self::$base_wenku_url . '?fr=bdpcindex&_wkts_=' . (time() * 1000 + rand(100, 999))
        ];
        return $referrers[array_rand($referrers)];
    }

    /**
     * @note 需要过滤的域名列表
     * @var array
     */
    private static $blockedDomains = [
        'pic.quanjing.com',      // 全景网图片
        // 可以继续添加其他需要过滤的域名
    ];


    /**
     * @note 生成现代化浏览器请求头
     * @param string $keyword 搜索关键词
     * @return array
     */
    private static function getModernHeaders($keyword): array
    {
        $userAgent = SpiderEnum::getRandomUserAgent();

        // 从User-Agent中提取浏览器信息用于生成sec-ch-ua
        $chromeVersion = '120'; // 默认版本
        if (preg_match('/Chrome\/(\d+)\./', $userAgent, $matches)) {
            $chromeVersion = $matches[1];
        }

        // 生成现代化sec-ch-ua头
        $secChUa = sprintf('"Not_A Brand";v="8", "Chromium";v="%s", "Google Chrome";v="%s"', $chromeVersion, $chromeVersion);

        // 随机决定是否添加可选请求头
        $optionalHeaders = [];
        if (rand(0, 1)) {
            $optionalHeaders['X-Requested-With'] = 'XMLHttpRequest';
        }
        if (rand(0, 2) === 0) {
            $optionalHeaders['Pragma'] = 'no-cache';
        }
        if (rand(0, 1)) {
            $optionalHeaders['DNT'] = '1';
        }

        $baseHeaders = [
            'Accept' => 'application/json, text/plain, */*',
            // 不设置Accept-Encoding，让CURLOPT_ENCODING完全控制编码处理
            'Accept-Language' => self::getRandomAcceptLanguage(),
            'Cache-Control' => 'no-cache',
            'Connection' => 'keep-alive',
            'Host' => 'image.baidu.com',
            'Referer' => self::getRandomReferer($keyword),

            // 🔥 现代浏览器安全头部
            'sec-ch-ua' => $secChUa,
            'sec-ch-ua-mobile' => '?0',
            'sec-ch-ua-platform' => self::getRandomPlatform(),
            'sec-ch-ua-platform-version' => self::getRandomPlatformVersion(),
            'sec-fetch-dest' => 'empty',
            'sec-fetch-mode' => 'cors',
            'sec-fetch-site' => 'same-origin',

            'User-Agent' => $userAgent,
            'Cookie' => self::generateRealisticCookie(),
        ];

        return array_merge($baseHeaders, $optionalHeaders);
    }

    /**
     * @note 随机生成Accept-Language头
     * @return string
     */
    private static function getRandomAcceptLanguage(): string
    {
        $languages = [
            'zh-CN,zh;q=0.9,en;q=0.8',
            'zh-CN,zh;q=0.9',
            'zh-CN,zh;q=0.9,en;q=0.8,ja;q=0.7',
            'zh-CN,zh-TW;q=0.9,zh;q=0.8,en;q=0.7',
        ];
        return $languages[array_rand($languages)];
    }

    /**
     * @note 随机生成平台信息
     * @return string
     */
    private static function getRandomPlatform(): string
    {
        $platforms = ['"Windows"', '"macOS"', '"Linux"'];
        return $platforms[array_rand($platforms)];
    }

    /**
     * @note 随机生成平台版本
     * @return string
     */
    private static function getRandomPlatformVersion(): string
    {
        $versions = [
            '"15.0.0"',  // Windows 11
            '"10.0.0"',  // Windows 10
            '"13.3.1"',  // macOS Ventura
            '"14.2.1"',  // macOS Sonoma
        ];
        return $versions[array_rand($versions)];
    }

    /**
     * @note 生成真实的百度Cookie (严格按照真实样本顺序)
     * @return string
     */
    private static function generateRealisticCookie(): string
    {
        $baseTime = time();

        // 🔥 按照真实Cookie顺序排列 (H_WISE_SIDS_BFESS在最前面)
        $cookies = [];

        // 1. 最重要的H_WISE_SIDS_BFESS (必须第一位)
        $wiseSids = self::generateWiseSidsBfess();
        $cookies[] = 'H_WISE_SIDS_BFESS=' . $wiseSids;

        // 2. 可选的MAWEBCUID (模拟真实)
        if (rand(0, 1)) {
            $cookies[] = 'MAWEBCUID=web_' . substr(md5(uniqid()), 0, 43);
        }

        // 3. 基础BAIDUID
        $cookies[] = 'BAIDUID=' . self::generateBaiduId() . ':FG=1';

        // 4. PSTM时间戳
        $cookies[] = 'PSTM=' . ($baseTime - rand(86400, 2592000));

        // 5. BIDUPSID
        $cookies[] = 'BIDUPSID=' . strtoupper(substr(md5(uniqid()), 0, 32));

        // 6. 固定BDORZ
        $cookies[] = 'BDORZ=FFFB88E999055A3F8A630C64834BD6D0';

        // 7. newlogin (可选)
        if (rand(0, 1)) {
            $cookies[] = 'newlogin=1';
        }

        // 8. BDUSS_BFESS (重要Cookie)
        if (rand(0, 1)) {
            $cookies[] = 'BDUSS_BFESS=' . self::generateBdussBfess();
        }

        // 9. MCITY
        $cookies[] = 'MCITY=-224%3A';

        // 10. BAIDUID_BFESS (与BAIDUID对应)
        $cookies[] = 'BAIDUID_BFESS=' . self::generateBaiduId() . ':FG=1';

        // 11. ZFY token
        $cookies[] = 'ZFY=' . self::generateZfyToken();

        // 12. arialoadData
        $cookies[] = 'arialoadData=false';

        // 13. BA_HECTOR
        $cookies[] = 'BA_HECTOR=' . self::generateBaHector();

        // 14. H_PS_PSSID (重要位置)
        $psSids = self::generatePsSsid();
        $cookies[] = 'H_PS_PSSID=' . $psSids;

        // 15. BDRCVFR
        $cookies[] = 'BDRCVFR[PWqFiQhMAWs]=9xWipS8B-FspA7EnHc1QhPEUf';

        // 16. PSINO
        $cookies[] = 'PSINO=' . rand(1, 10);

        // 17. delPer
        $cookies[] = 'delPer=0';

        // 18. H_WISE_SIDS (简化版，可选)
        if (rand(0, 1)) {
            $shortSids = [];
            for ($i = 0; $i < rand(15, 25); $i++) {
                $shortSids[] = rand(60000, 65000);
            }
            $cookies[] = 'H_WISE_SIDS=' . implode('_', $shortSids);
        }

        // 19. ab_sr (最后)
        $cookies[] = 'ab_sr=1.0.1_' . self::generateAbSr();

        return implode('; ', $cookies);
    }

    /**
     * @note 生成BAIDUID格式 (32位十六进制)
     */
    private static function generateBaiduId(): string
    {
        return strtoupper(substr(md5(uniqid(mt_rand(), true)), 0, 32));
    }

    /**
     * @note 生成高仿真H_WISE_SIDS_BFESS (精确基于真实样本)
     */
    private static function generateWiseSidsBfess(): string
    {
        $sids = [];

        // 🔥 开头固定低位数字 (10万-40万，模拟真实开头)
        for ($i = 0; $i < rand(8, 15); $i++) {
            $sids[] = rand(100000, 400000);
        }

        // 🔥 核心范围：60万-63万 (真实样本的主要特征)
        for ($i = 0; $i < rand(35, 50); $i++) {
            $sids[] = rand(600000, 630000);
        }

        // 🔥 199万高位数字 (精确模拟真实特征)
        for ($i = 0; $i < rand(8, 12); $i++) {
            $sids[] = rand(1991000, 1992999);
        }

        // 🔥 少量31万-62万补充 (模拟真实分布)
        for ($i = 0; $i < rand(5, 10); $i++) {
            $sids[] = rand(310000, 620000);
        }

        // 🔥 少量61万-62.5万精确范围
        for ($i = 0; $i < rand(10, 20); $i++) {
            $sids[] = rand(610000, 625000);
        }

        // 保持原始顺序，不打乱 (更接近真实Cookie)
        return implode('_', $sids);
    }

    /**
     * @note 生成H_PS_PSSID (精确基于真实样本60272-64668)
     */
    private static function generatePsSsid(): string
    {
        $psids = [];
        // 真实样本范围: 60272_62325_63145_63325_63948_64248_64364_64415_64436_64440_64450_64460_64475_64504_64513_64086_64554_64565_64591_64595_64597_64601_64629_64631_64649_64668
        for ($i = 0; $i < rand(20, 25); $i++) {
            $psids[] = rand(60200, 64700); // 精确模拟真实范围
        }
        return implode('_', $psids);
    }

    /**
     * @note 生成ZFY token
     */
    private static function generateZfyToken(): string
    {
        $chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
        $token = '';
        for ($i = 0; $i < 43; $i++) {
            $token .= $chars[rand(0, strlen($chars) - 1)];
        }
        return $token . ':C';
    }

    /**
     * @note 生成BA_HECTOR
     */
    private static function generateBaHector(): string
    {
        return dechex(rand(100000000, 999999999)) . dechex(rand(10000000, 99999999)) .
            dechex(rand(1000000, 9999999)) . dechex(rand(100000, 999999)) .
            'a' . dechex(rand(100, 999)) . 'a' . dechex(rand(1000000, 9999999));
    }

    /**
     * @note 生成ab_sr token
     */
    private static function generateAbSr(): string
    {
        return base64_encode(hash('sha256', uniqid(mt_rand(), true) . microtime(), true));
    }

    /**
     * @note 生成BDUSS_BFESS token
     */
    private static function generateBdussBfess(): string
    {
        return base64_encode(substr(hash('sha256', uniqid() . time()), 0, 43));
    }


    /**
     * @note 检查URL是否包含被屏蔽的域名
     * @param string $url 要检查的URL
     * @return bool true表示需要过滤掉，false表示可以保留
     */
    private static function isBlockedDomain($url)
    {
        if (empty($url)) {
            return true; // 空URL直接过滤
        }

        // 解析URL获取域名
        $parsedUrl = parse_url($url);
        if (!isset($parsedUrl['host'])) {
            return true; // 无法解析域名的URL过滤掉
        }

        $host = strtolower($parsedUrl['host']);

        // 检查是否在屏蔽域名列表中
        foreach (self::$blockedDomains as $blockedDomain) {
            if ($host === $blockedDomain || str_ends_with($host, '.' . $blockedDomain)) {
                return true;
            }
        }

        return false;
    }


    /**
     * @note 百度图片搜索API（性能优化版）
     * @param string $keyword 搜索关键词
     * @param int $limit 图片数量限制 默认取30张以提高筛选成功率
     * @param int $showSize 限制显示数量
     * @return array
     */
    public static function fetchImageList($keyword, $limit = 30, $showSize = 4)
    {
        // Step 1: 获取候选图片链接，如果没有数据就重试百度API请求
        $candidateUrls = self::getBaiduImageUrls($keyword, $limit);
        // 如果第一次请求百度API没有获取到数据，重试一次
        if (empty($candidateUrls)) {
            $candidateUrls = self::getBaiduImageUrls($keyword, $limit);
        }

        // 如果重试后还是没有数据，直接返回空数组
        if (empty($candidateUrls)) {
            return [];
        }
        // Step 2: 基于候选URL进行检测，这里不需要重试了
        return self::processImageUrls($candidateUrls, $showSize);
    }

    /**
     * @note 处理图片URL检测（核心检测逻辑，支持重试而不重复网络请求）
     * @param array $candidateUrls 候选图片URL数组
     * @param int $showSize 需要的图片数量
     * @return array
     */
    private static function processImageUrls($candidateUrls, $showSize)
    {
        try {
            $candidateCount = count($candidateUrls);
            if (empty($candidateUrls)) {
                return [];
            }

            // Step 1: 两轮检测策略 - 优先满足第一轮，不足时第二轮检测剩余
            // 方案B：动态检测 + 提前退出的渐进式策略
            // 第一轮检测数量：需求数量的1.5倍，确保高成功率同时支持提前退出
            if ($candidateCount <= $showSize) {
                // 候选数量不足需求，全部检测
                $firstRoundCount = $candidateCount;
            } else {
                // 渐进式检测：第一轮检测需求数量的1.5倍（如需要4个，检测6个）
                $firstRoundCount = intval($showSize * 1.5);
                $firstRoundCount = max($firstRoundCount, 4); // 最少检测4个
                $firstRoundCount = min($firstRoundCount, 8); // 第一轮最多8个
                $firstRoundCount = min($firstRoundCount, $candidateCount); // 不超过候选总数
            }


            $checkUrls = array_slice($candidateUrls, 0, $firstRoundCount);
            // Step 2: 第一轮检测（处理0+4模式的特殊情况）
            $checkResults = [];
            if ($firstRoundCount > 0) {
                $checkResults = self::checkImageStatusBatch($checkUrls);
            }
            // 如果第一轮检测0个URL（0+4模式），checkResults为空数组
            // Step 3: 筛选第一轮有效的URL（强化提前退出机制）
            $validUrls = [];
            if (!empty($checkResults)) {
                foreach ($checkResults as $result) {
                    if (isset($result['status']) && $result['status'] == true) {
                        $validUrls[] = $result['url'];
                        // 关键：找到足够数量立即退出，实现真正的动态检测
                        if (count($validUrls) >= $showSize) {
                            break; // 提前退出，不再处理剩余检测结果
                        }
                    }
                }
            }
            // Step 4: 第二轮检测逻辑（满足用户要求：第一轮足够则不进行第二轮）
            // 如果第一轮检测结果不足且还有剩余URL，进行第二轮检测
            if (count($validUrls) < $showSize && $candidateCount > $firstRoundCount) {
                $remainingUrls = array_slice($candidateUrls, $firstRoundCount);
                $neededCount = $showSize - count($validUrls);

                // 第二轮检测数量：精准控制，避免过度检测
                $maxSecondRound = min(count($remainingUrls), 6); // 第二轮最多检测6个
                // 按需求数量的2倍检测，但不超过剩余URL数量和上限
                $secondRoundCount = min($maxSecondRound, max($neededCount * 2, 4)); // 至少检测4个，提高成功率

                if ($secondRoundCount > 0) {
                    $additionalCheckUrls = array_slice($remainingUrls, 0, $secondRoundCount);
                    $additionalResults = self::checkImageStatusBatch($additionalCheckUrls);

                    // 从第二轮检测结果中筛选有效URL
                    foreach ($additionalResults as $result) {
                        if (isset($result['status']) && $result['status'] == true) {
                            $validUrls[] = $result['url'];
                            if (count($validUrls) >= $showSize) {
                                break; // 第二轮找到足够数量就停止
                            }
                        }
                    }
                }
            }

            // 重要：无论第二轮检测结果如何，都不再进行额外检测
            // 严格遵循两轮检测原则
            return array_slice($validUrls, 0, $showSize);

        } catch (\Exception $e) {
            return [];
        }
    }


    /**
     * @note 百度图片专用HTTP请求 - 解决编码问题
     * @param string $url 请求URL
     * @param array $headers 请求头
     * @return \GuzzleHttp\Psr7\Response|\Psr\Http\Message\ResponseInterface
     */
    private static function sendBaiduRequest($url, $headers = [])
    {
        $client = GeneralFunction::getHttpClient();

        // 百度图片专用：完全移除Accept-Encoding，依赖CURLOPT_ENCODING控制
        $cleanHeaders = $headers;
        
        // 调试输出：显示处理前后的Accept-Encoding信息
        echo "<br/>原始Accept-Encoding: " . ($headers['Accept-Encoding'] ?? 'undefined') . "<br/>";
        
        unset($cleanHeaders['Accept-Encoding']);  // 不设置任何编码头
        
        echo "<br/>处理后Accept-Encoding: " . ($cleanHeaders['Accept-Encoding'] ?? 'undefined') . "<br/>";
        echo "<br/>发送请求，无Accept-Encoding头，由CURLOPT_ENCODING控制编码...<br/>";

        try {
            // 主请求：依赖GeneralFunction的全局CURLOPT_ENCODING设置
            return $client->get($url, ['headers' => $cleanHeaders]);
        } catch (RequestException $e) {
            // 如果是编码错误，使用最大兼容模式重试
            if (strpos($e->getMessage(), 'Unrecognized content encoding') !== false) {
                // 最大兼容模式：强制使用最基础的HTTP配置
                return $client->get($url, [
                    'headers' => $cleanHeaders,
                    'curl' => [
                        CURLOPT_ENCODING => '',                    // 再次确认禁用编码
                        CURLOPT_HTTP_VERSION => CURL_HTTP_VERSION_1_0, // HTTP 1.0最大兼容
                        CURLOPT_FOLLOWLOCATION => false,           // 禁用重定向
                        CURLOPT_MAXREDIRS => 0,                   // 不允许重定向
                    ],
                    'decode_content' => false,                     // 再次确认禁用解码
                    'timeout' => 30,
                ]);
            }
            throw $e;
        }
    }

    /**@note 从百度图片搜索接口获取原始图片 URL 列表
     * @param string $keyword
     * @param int $limit
     * @return array
     */
    private static function getBaiduImageUrls($keyword, $limit)
    {
        $keyword = trim($keyword);
        $apiUrl = 'https://image.baidu.com/search/acjson?tn=resultjson_com&word=' . urlencode($keyword) . '&pn=0&z=4&rn=' . $limit;
        echo "<br/>URL: {$apiUrl}<br/>";

        // 使用现代化请求头
        $headers = self::getModernHeaders($keyword);

        try {
            // 使用百度图片专用请求方法
            $response = self::sendBaiduRequest($apiUrl, $headers);
            $httpCode = $response->getStatusCode();
            $body = $response->getBody()->getContents();

            process_response:
            // 线上调试信息收集
            $debugInfo = [
                'url' => $apiUrl,
                'http_code' => $httpCode,
                'user_agent' => $headers['User-Agent'],
                'referer' => $headers['Referer'],
                'response_length' => strlen($body),
                'response_preview' => substr($body, 0, 500),
            ];

            // HTTP状态码检查
            if ($httpCode !== 200) {
                throw new \Exception("百度图片API请求失败 - HTTP状态码: {$httpCode}, URL: {$apiUrl}, 响应内容: " . substr($body, 0, 200));
            }

            // 响应内容检查
            if (empty($body)) {
                throw new \Exception("百度图片API返回空响应 - URL: {$apiUrl}, HTTP状态码: {$httpCode}");
            }

            $data = json_decode($body, true);
            // JSON解析检查
            if (json_last_error() !== JSON_ERROR_NONE) {
                throw new \Exception("百度图片API返回非JSON格式 - JSON错误: " . json_last_error_msg() . ", 响应内容: " . substr($body, 0, 300));
            }

            // 反爬检测 - 统一检查
            if (isset($data['antiFlag']) && $data['antiFlag'] == 1) {
                $message = $data['message'] ?? '未知反爬限制';
                $bfeLogId = $data['bfe_log_id'] ?? '无日志ID';
                throw new \Exception("百度反爬限制触发 - {$message}, BFE日志ID: {$bfeLogId}, 建议更换IP或降低请求频率");
            }

            // 数据结构检查
            if (!isset($data['data'])) {
                throw new \Exception("百度图片API数据结构异常 - 缺少data字段, 完整响应: " . json_encode($data, JSON_UNESCAPED_UNICODE));
            } else {
                echo " <br />匹配到 data数据的结构 <br />";
            }

            //数据检查
            if (empty($data['data'])) {
                throw new \Exception("百度图片API返回空数据 - 可能被反爬限制或关键词无结果, 关键词: {$keyword}, 响应: " . json_encode($data, JSON_UNESCAPED_UNICODE));
            } else {
                echo " <br />匹配到data有值的数据情况 " . var_export($data['data'], true) . " <br/>";
            }


            $urls = [];
            $totalItems = count($data['data']);
            $validUrls = 0;

            foreach ($data['data'] ?? [] as $item) {
                if (!empty($item['replaceUrl'])) {
                    $objurl = $item['replaceUrl'][0]['ObjURL'] ?? '';

                    // 过滤掉百度代理链接（含有src=参数的）
                    if (strpos($objurl, 'src=') !== false) {
                        continue;
                    }

                    //只匹配主流的图片格式
                    if (preg_match('/(.*\.(?:jpe?g|png|gif|bmp|webp))/i', $objurl, $matches)) {
                        $urls[] = $matches[1];
                        $validUrls++;
                    }
                }
            }

            // 结果检查
            if (empty($urls)) {
                throw new \Exception("百度图片API解析结果为空 - 总条目: {$totalItems}, 有效URL: {$validUrls}, 调试信息: " . json_encode($debugInfo, JSON_UNESCAPED_UNICODE));
            }

            return $urls;

        } catch (ConnectException $e) {
            throw new \Exception("百度图片API连接失败 - 网络问题: " . $e->getMessage() . ", URL: {$apiUrl}");
        } catch (RequestException $e) {
            throw new \Exception("百度图片API请求异常 - Guzzle错误: " . $e->getMessage() . ", URL: {$apiUrl}");
        } catch (\Exception $e) {
            // 如果是我们主动抛出的异常，直接向上传递
            if (strpos($e->getMessage(), '百度图片API') !== false) {
                throw $e;
            }
            // 其他未知异常
            throw new \Exception("百度图片API未知异常 - " . $e->getMessage() . ", URL: {$apiUrl}");
        }
    }


    /**
     * 批量检测图片URL的有效性
     * 支持并发检测，自动判断403、404等情况
     * 建议每批30-50个URL
     *
     * @param array $urls 图片URL数组
     * @return array ['url1'=>bool, ...] true=可用，false=不可用/403/404等
     */
    public static function checkImageStatusBatch($urls)
    {
        if (!$urls || empty($urls)) {
            return [];
        }

        try {
            $multiCurl = curl_multi_init();
            $handles = [];
            $results = [];

            foreach ($urls as $index => $url) {
                $ch = curl_init();
                curl_setopt_array($ch, [
                    CURLOPT_URL => $url,
                    CURLOPT_RETURNTRANSFER => true,
                    CURLOPT_FOLLOWLOCATION => true,
                    CURLOPT_TIMEOUT => 3,
                    CURLOPT_USERAGENT => SpiderEnum::getRandomUserAgent(),
                    CURLOPT_SSL_VERIFYPEER => false,
                    CURLOPT_HEADER => true,
                    CURLOPT_RANGE => '0-2047', // 只取2KB
                ]);
                curl_multi_add_handle($multiCurl, $ch);
                $handles[$index] = ['url' => $url, 'handle' => $ch];
            }

            $running = 0;
            do {
                curl_multi_exec($multiCurl, $running);
                if ($running > 0) {
                    usleep(10000);
                }
            } while ($running > 0);

            foreach ($handles as $index => $item) {
                $ch = $item['handle'];
                $url = $item['url'];
                $response = curl_multi_getcontent($ch);
                $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
                $contentType = curl_getinfo($ch, CURLINFO_CONTENT_TYPE);
                $headerSize = curl_getinfo($ch, CURLINFO_HEADER_SIZE);
                $body = substr($response, $headerSize);
                $body = ltrim($body);
                if (
                    ($httpCode >= 200 && $httpCode < 300) && // 支持所有2xx成功状态码
                    strpos($contentType, 'image/') === 0 &&
                    strlen($body) > 200 &&
                    !preg_match('/403 Forbidden|404 Not Found|Error 404|Access Denied|抱歉|禁止访问|error|denied|防盗链|hotlink|页面不存在|找不到文件/i', $body) &&
                    !preg_match('/^\s*\{.*\}\s*$/s', $body) && // JSON
                    !preg_match('/^\s*\<(!DOCTYPE|html|body)/i', $body) && // HTML
                    self::isValidImageHeader($body) // 验证图片文件头
                ) {
                    $status = true;//成功的状态的url
                } else {
                    $status = false;//失败的状态url

                }

                $results[] = [
                    'url' => $url,
                    'httpCode' => $httpCode,
                    'status' => $status,//获取是否为正常的访问链接
                ];
                curl_multi_remove_handle($multiCurl, $ch);
                curl_close($ch);
            }

            curl_multi_close($multiCurl);
            return $results;

        } catch (\Exception $e) {
            return [];
        }
    }

    /**
     * @note 验证图片文件头是否有效
     * @param string $body 响应内容
     * @return bool true=有效图片文件头，false=无效
     */
    private static function isValidImageHeader($body)
    {
        if (strlen($body) < 8) {
            return false;
        }
        $header = substr($body, 0, 12); // 取前12字节足够检测所有格式

        return (
            // JPEG: FF D8 FF
            substr($header, 0, 3) === "\xFF\xD8\xFF" ||
            // PNG: 89 50 4E 47 0D 0A 1A 0A
            substr($header, 0, 4) === "\x89\x50\x4E\x47" ||
            // GIF87a
            substr($header, 0, 6) === "GIF87a" ||
            // GIF89a
            substr($header, 0, 6) === "GIF89a" ||
            // WebP: RIFF xxxx WEBP
            (substr($header, 0, 4) === "RIFF" && substr($header, 8, 4) === "WEBP") ||
            // BMP: BM
            substr($header, 0, 2) === "BM" ||
            // TIFF: II* (little endian) or MM* (big endian)
            substr($header, 0, 4) === "II*\x00" ||
            substr($header, 0, 4) === "MM\x00*" ||
            // ICO: 00 00 01 00
            substr($header, 0, 4) === "\x00\x00\x01\x00" ||
            // SVG: <?xml or <svg
            (substr($header, 0, 5) === "<?xml" && strpos($body, "<svg") !== false) ||
            substr($header, 0, 4) === "<svg"
        );
    }


}